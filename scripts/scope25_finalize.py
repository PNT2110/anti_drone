#!/usr/bin/env python3
"""Create the Scope 25 package only after a passing Pi reproduction smoke."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope25"
PACKAGE = ROOT / "artifacts" / "production-candidate" / "scope25"
BEST = ROOT / "artifacts/experiments/scope18-v3-labelrepair/scope18-yolov8n-480/attempt-batch16/weights/best.pt"
SOURCE_NCNN = ROOT / "artifacts/exports/scope19/scope18-yolov8n-480/float32/ncnn/model_ncnn_model"

EXPECTED = {
    "best.pt": "359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e",
    "model.ncnn.param": "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5",
    "model.ncnn.bin": "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def main() -> int:
    audit = json.loads((RUNTIME / "input_audit.json").read_text())
    smoke = json.loads((RUNTIME / "pi_smoke_result.json").read_text())
    if audit["candidate_id"] != "scope18-yolov8n-480:ncnn":
        raise SystemExit("BLOCKED_FREEZE_INPUT_CHANGED: candidate id")
    actual = {
        "best.pt": sha256(BEST),
        "model.ncnn.param": sha256(SOURCE_NCNN / "model.ncnn.param"),
        "model.ncnn.bin": sha256(SOURCE_NCNN / "model.ncnn.bin"),
    }
    if actual != EXPECTED:
        raise SystemExit(json.dumps({"status": "BLOCKED_FREEZE_INPUT_CHANGED", "expected": EXPECTED, "actual": actual}, indent=2))
    if smoke.get("status") != "SMOKE_PASS" or smoke.get("test_accessed") is not False:
        raise SystemExit("FREEZE_REPRODUCTION_FAIL: smoke status or TEST boundary")
    if smoke.get("candidate_id") != audit["candidate_id"] or smoke.get("warmup_passes") != 20 or smoke.get("measured_passes") != 20:
        raise SystemExit("FREEZE_REPRODUCTION_FAIL: reproduction protocol mismatch")
    if smoke.get("hardware", {}).get("machine") != "aarch64" or "Raspberry Pi 5 Model B Rev 1.0" not in smoke.get("hardware", {}).get("model", ""):
        raise SystemExit("PI_IDENTITY_FAIL")
    if smoke.get("runtime", {}).get("runtime") != "ncnn" or smoke.get("runtime", {}).get("version") != "1.0.20260526" or smoke.get("runtime", {}).get("threads") != 4:
        raise SystemExit("FREEZE_REPRODUCTION_FAIL: runtime contract")
    if len(smoke.get("images", [])) != 8 or any(x.get("parity", {}).get("status") != "PARITY_PASS" for x in smoke["images"]):
        raise SystemExit("FREEZE_REPRODUCTION_FAIL: fixed-input parity")
    for name, digest in EXPECTED.items():
        if name != "best.pt" and smoke["artifact_hashes"][name]["actual"] != digest:
            raise SystemExit("FREEZE_REPRODUCTION_FAIL: Pi artifact hash")
    if PACKAGE.exists():
        raise SystemExit(f"BLOCKED_PACKAGE_EXISTS_REVIEW_REQUIRED: {PACKAGE}")

    timestamp = datetime.now(timezone.utc).isoformat()
    preprocess = {
        "contract_version": "scope25-preprocess-v1",
        "input_color": "OpenCV BGR",
        "color_conversion": "BGR_to_RGB",
        "letterbox": {"rect": False, "target_width": 480, "target_height": 480, "padding": 114, "interpolation": "INTER_LINEAR"},
        "dtype": "float32",
        "normalization": "divide_by_255",
        "tensor_layout": "NCHW",
        "batch": 1,
    }
    postprocess = {
        "contract_version": "scope25-postprocess-v1",
        "raw_output": "[1,5,N]",
        "interpretation": "xywh_plus_single_class_confidence",
        "class_id": 0,
        "confidence_threshold": 0.25,
        "nms_iou": 0.70,
        "external_nms": "exactly_once",
    }
    runtime = {
        "backend": "NCNN",
        "precision": "FP32",
        "version": "1.0.20260526",
        "threads": 4,
        "target_hardware": "Raspberry Pi 5 Model B Rev 1.0",
        "architecture": "aarch64",
        "ram_class": "4 GiB",
    }
    package_manifest = {
        "candidate_id": audit["candidate_id"],
        "model_family": "yolov8n",
        "training_run": "scope18-yolov8n-480",
        "best_epoch": 82,
        "training_imgsz": 480,
        "deployment_imgsz": 480,
        "source_best_pt_sha256": EXPECTED["best.pt"],
        "ncnn_param_sha256": EXPECTED["model.ncnn.param"],
        "ncnn_bin_sha256": EXPECTED["model.ncnn.bin"],
        "dataset_manifest_sha256": audit["dataset_manifest_sha256"],
        "split_registry_sha256": audit["split_registry_sha256"],
        "class_count": 1,
        "class_names": ["drone"],
        "class_id": 0,
        "confidence_threshold": 0.25,
        "nms_iou": 0.70,
        "preprocess": preprocess,
        "postprocess": postprocess,
        "backend": "NCNN",
        "backend_version": "1.0.20260526",
        "threads": 4,
        "precision": "FP32",
        "pi_hardware": "Raspberry Pi 5 Model B Rev 1.0",
        "frozen_val_metrics": audit["frozen_val"],
        "scope21_pi_benchmark_reference": {"status": "PI_BENCHMARK_PASS", "fps": audit["scope21_pi_fps"], "model_bytes": audit["scope21_pi_model_bytes"]},
        "scope25r_reproduction_reference": {
            "status": "PI_REPRODUCTION_PASS",
            "evidence_sha256": sha256(RUNTIME / "pi_smoke_result.json"),
            "images": 8,
            "warmup_passes": smoke["warmup_passes"],
            "measured_passes": smoke["measured_passes"],
            "max_confidence_abs": max(x["parity"]["max_confidence_abs"] for x in smoke["images"]),
            "min_bbox_iou": min(x["parity"]["min_bbox_iou"] for x in smoke["images"]),
        },
        "int8_status": "PTQ_INT8_PATHS_EXHAUSTED_FOR_CURRENT_SCOPE",
        "freeze_timestamp": timestamp,
        "test_accessed": False,
    }
    provenance = {
        "candidate_id": audit["candidate_id"],
        "source_best_pt": str(BEST),
        "source_ncnn_dir": str(SOURCE_NCNN),
        "scope20_parity": "PARITY_PASS",
        "scope21_pi_benchmark": "PI_BENCHMARK_PASS",
        "scope25r_route": "LAN SSH 192.168.1.118",
        "scope25r_workspace": "/home/pitan/antidrone-scope25-smoke",
        "scope25r_evidence": str(RUNTIME / "pi_smoke_result.json"),
        "source_artifacts_regenerated": False,
        "test_accessed": False,
        "freeze_timestamp": timestamp,
    }

    PACKAGE.mkdir(parents=True)
    shutil.copy2(SOURCE_NCNN / "model.ncnn.param", PACKAGE / "model.ncnn.param")
    shutil.copy2(SOURCE_NCNN / "model.ncnn.bin", PACKAGE / "model.ncnn.bin")
    write_json(PACKAGE / "model_manifest.json", package_manifest)
    write_json(PACKAGE / "preprocess_contract.json", preprocess)
    write_json(PACKAGE / "postprocess_contract.json", postprocess)
    write_json(PACKAGE / "runtime_contract.json", runtime)
    write_json(PACKAGE / "provenance.json", provenance)

    package_files = sorted(p for p in PACKAGE.iterdir() if p.is_file())
    sums = "".join(f"{sha256(path)}  {path.name}\n" for path in package_files)
    (PACKAGE / "SHA256SUMS").write_text(sums)
    package_files = sorted(p for p in PACKAGE.iterdir() if p.is_file())
    package_hashes = {p.name: sha256(p) for p in package_files}
    freeze = {
        "status": "FP32_NCNN_CANDIDATE_FROZEN",
        "candidate_id": audit["candidate_id"],
        "package_dir": str(PACKAGE),
        "package_file_sha256": package_hashes,
        "source_best_pt_sha256": EXPECTED["best.pt"],
        "ncnn_param_sha256": EXPECTED["model.ncnn.param"],
        "ncnn_bin_sha256": EXPECTED["model.ncnn.bin"],
        "preprocess_contract_sha256": sha256(PACKAGE / "preprocess_contract.json"),
        "postprocess_contract_sha256": sha256(PACKAGE / "postprocess_contract.json"),
        "runtime_contract_sha256": sha256(PACKAGE / "runtime_contract.json"),
        "dataset_manifest_sha256": audit["dataset_manifest_sha256"],
        "split_registry_sha256": audit["split_registry_sha256"],
        "pi_reproduction_evidence_sha256": sha256(RUNTIME / "pi_smoke_result.json"),
        "int8_status": "PTQ_INT8_PATHS_EXHAUSTED_FOR_CURRENT_SCOPE",
        "freeze_timestamp": timestamp,
        "test_accessed": False,
    }
    freeze_path = RUNTIME / "scope25_freeze_manifest.json"
    write_json(freeze_path, freeze)
    freeze_hash = sha256(freeze_path)
    (RUNTIME / "scope25_freeze_manifest.sha256").write_text(f"{freeze_hash}  {freeze_path.name}\n")
    write_json(RUNTIME / "freeze_status.json", {"status": freeze["status"], "candidate_id": freeze["candidate_id"], "package_created": True, "freeze_manifest_created": True, "freeze_manifest_sha256": freeze_hash, "test_accessed": False})
    print(json.dumps({"status": freeze["status"], "package": str(PACKAGE), "freeze_manifest_sha256": freeze_hash, "package_file_sha256": package_hashes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
