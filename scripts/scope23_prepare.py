#!/usr/bin/env python3
"""Freeze Scope 23 plan, diagnostic membership, and exact-input calibration sets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope21_pi_runner import preprocess  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope23"
SCOPE19 = ROOT / ".runtime/scope19"
SCOPE20 = ROOT / ".runtime/scope20"
SCOPE22 = ROOT / ".runtime/scope22"
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate/images/train"
APPROVED = [("scope18-yolov8n-480", 480), ("scope18-yolov8n-640", 640), ("scope18-yolov11n-480", 480)]


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_paths(paths: list[str]) -> str:
    return digest_bytes(("\n".join(paths) + "\n").encode())


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    calibration = json.loads((SCOPE19 / "calibration_manifest.json").read_text())
    benchmark = json.loads((SCOPE19 / "benchmark_input_manifest.json").read_text())
    all_train = sorted(str(p) for p in DATASET.glob("*.jpg"))
    baseline_paths = sorted(calibration["paths"])
    baseline_set = set(baseline_paths)
    secondary_paths = [p for p in all_train if p not in baseline_set][:32]
    if len(secondary_paths) != 32:
        raise RuntimeError("could not create 32-image train-only secondary set outside baseline calibration")
    expanded_paths = baseline_paths + [p for p in all_train if p not in baseline_set][:128]
    if len(expanded_paths) != 256:
        raise RuntimeError("could not create deterministic 256-image train-only calibration set")

    sets = {"128": baseline_paths, "256": sorted(expanded_paths)}
    manifests = {}
    input_contract = {"runtime": "Scope21 preprocess", "color": "cv2 BGR -> RGB", "normalization": "/255", "letterbox": "rect=False, constant 114", "tensor_order": "NCHW", "records": []}
    for run_id, size in APPROVED:
        representative = Path(benchmark["paths"][0])
        image = cv2.imread(str(representative))
        tensor, gain, pad = preprocess(image, size)
        input_contract["records"].append({"run_id": run_id, "size": size, "image": representative.name, "shape": list(tensor.shape), "dtype": str(tensor.dtype), "min": float(tensor.min()), "max": float(tensor.max()), "mean": float(tensor.mean()), "tensor_sha256": digest_bytes(np.ascontiguousarray(tensor).tobytes()), "representative_first_pixel_chw": tensor[0, :, 0, 0].tolist(), "gain": gain, "pad": list(pad)})
        for count, paths in sets.items():
            npy_dir = RUNTIME / "calibration_npy" / f"{count}" / run_id
            npy_dir.mkdir(parents=True, exist_ok=True)
            npy_paths = []
            for index, path in enumerate(paths):
                img = cv2.imread(path)
                tensor, _, _ = preprocess(img, size)
                out = npy_dir / f"{index:04d}.npy"
                np.save(out, tensor[0].astype(np.float32), allow_pickle=False)
                npy_paths.append(str(out))
            manifest = {"experiment_input": "exact Scope21 preprocess tensor", "count": int(count), "source_split": "train", "test_accessed": False, "sample_paths": paths, "sample_ids": [Path(p).name for p in paths], "sample_membership_sha256": digest_paths(paths), "npy_paths": npy_paths, "run_id": run_id, "size": size, "npy_shape": [3, size, size], "dtype": "float32"}
            manifest_path = RUNTIME / "calibration_manifests" / f"{run_id}_{count}.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True); manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            manifests[f"{run_id}:{count}"] = str(manifest_path)

    secondary = {"count": 32, "source_split": "train", "test_accessed": False, "selection_rule": "sorted processed-train JPG paths excluding the locked 128-image calibration membership; first 32", "paths": secondary_paths, "sample_ids": [Path(p).name for p in secondary_paths], "membership_sha256": digest_paths(secondary_paths)}
    (RUNTIME / "secondary_diagnostic_manifest.json").write_text(json.dumps(secondary, indent=2) + "\n")
    (RUNTIME / "input_contract.json").write_text(json.dumps(input_contract, indent=2) + "\n")
    plan = {
        "status": "FROZEN_BEFORE_RESULTS",
        "approved_candidates": [f"{run_id}:ncnn" for run_id, _ in APPROVED],
        "primary_candidates": ["scope18-yolov8n-640:ncnn", "scope18-yolov8n-480:ncnn"],
        "secondary_confirmation": "scope18-yolov11n-480:ncnn only after a v8 method passes",
        "fixed_thresholds": {"confidence": 0.25, "nms_iou": 0.70},
        "primary_acceptance": {"detection_count_mismatch_max": 0, "class_mismatch_max": 0, "minimum_bbox_iou": 0.90, "maximum_confidence_abs": 0.20},
        "secondary_acceptance": {"count_mismatch_max": 0, "class_mismatch_max": 0, "minimum_bbox_iou": 0.90, "maximum_confidence_abs": 0.20, "no_systematic_detection_loss": True},
        "diagnostic_sets": {"fixed_8": {"manifest": str(SCOPE19 / "benchmark_input_manifest.json"), "count": 8, "split": "train", "test_accessed": False}, "secondary_32": str(RUNTIME / "secondary_diagnostic_manifest.json")},
        "calibration_manifest_scope22_sha256": "4c582deab8ec13a23a0ecf0b1b806e6f3dd0c2c43f5a7dca06c785227e444b59",
        "calibration_sets": {"128": {"membership_sha256": digest_paths(baseline_paths), "source_split": "train"}, "256": {"membership_sha256": digest_paths(sorted(expanded_paths)), "source_split": "train"}},
        "experiments": [
            {"id": "E0", "scope22_baseline": True, "candidates": ["v8n-480", "v8n-640", "v11n-480"], "method": "kl", "calibration_count": 128, "preprocess": "raw image direct resize from ncnn2table; Scope22 baseline; diagnostic reference only"},
            {"id": "E1", "scope22_baseline": False, "candidates": ["v8n-480", "v8n-640"], "method": "kl", "calibration_count": 128, "preprocess": "type=1 exact Scope21 NCHW float32 tensor saved as NPY", "stop_rule": "if both primary v8 candidates pass, do not run E2/E3"},
            {"id": "E2", "scope22_baseline": False, "candidates": ["v8n-480", "v8n-640"], "method": "kl", "calibration_count": 256, "preprocess": "type=1 exact Scope21 NCHW float32 tensor saved as NPY", "stop_rule": "run only if E1 does not pass both primary candidates"},
            {"id": "E3", "scope22_baseline": False, "candidates": ["v8n-480", "v8n-640"], "method": "aciq", "calibration_count": 128, "preprocess": "type=1 exact Scope21 NCHW float32 tensor saved as NPY", "stop_rule": "run only if E1/E2 do not pass both primary candidates"},
        ],
        "tool_supported_methods": ["kl", "aciq", "eq"],
        "max_configurations_per_primary": 4,
        "no_test": True,
    }
    (RUNTIME / "experiment_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"status": plan["status"], "secondary_count": 32, "calibration_sets": manifests, "plan": str(RUNTIME / "experiment_plan.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
