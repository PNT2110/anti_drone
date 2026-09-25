#!/usr/bin/env python3
"""Freeze Scope 24 inputs and create exact TRAIN calibration representations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope24"
SCOPE23 = ROOT / ".runtime" / "scope23"
SCOPE19 = ROOT / ".runtime" / "scope19"
TFLITE_VENV = Path("/home/pnt/.venvs/antidrone_scope24_tflite")
CALIBRATION_DIR = Path("/home/pnt/.cache/antidrone_scope24_calibration")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    plan = {
        "status": "FROZEN_BEFORE_RESULTS",
        "scope": "24",
        "test_access": False,
        "candidates": [
            {"run_id": "scope18-yolov8n-480", "size": 480, "onnx": str(ROOT / "artifacts/exports/scope19/scope18-yolov8n-480/float32/onnx/model.onnx")},
            {"run_id": "scope18-yolov8n-640", "size": 640, "onnx": str(ROOT / "artifacts/exports/scope19/scope18-yolov8n-640/float32/onnx/model.onnx")},
        ],
        "calibration": {
            "manifest": str(SCOPE19 / "calibration_manifest.json"),
            "manifest_sha256": "4c582deab8ec13a23a0ecf0b1b806e6f3dd0c2c43f5a7dca06c785227e444b59",
            "source_split": "train",
            "count": 128,
            "representation": "exact Scope21/23 float32 NCHW tensors transposed to NHWC for onnx2tf",
            "test_accessed": False,
        },
        "diagnostic_sets": {
            "fixed_8": {"manifest": str(SCOPE19 / "benchmark_input_manifest.json"), "count": 8, "split": "train", "test_accessed": False},
            "secondary_32": {"manifest": str(SCOPE23 / "secondary_diagnostic_manifest.json"), "count": 32, "source_split": "train", "test_accessed": False},
        },
        "preprocess": {
            "source": "BGR",
            "color": "RGB",
            "letterbox": "rect=False, constant 114",
            "normalization": "/255",
            "tensor_order_runtime": "NCHW",
            "tensor_order_converter_calibration": "NHWC",
            "batch": 1,
        },
        "tflite_paths": [
            {"id": "T1", "converter": "onnx2tf", "backend": "flatbuffer_direct", "quantization": "full_integer_quant", "input_dtype": "int8", "output_dtype": "int8", "max_per_model": 1},
            {"id": "T2", "converter": "onnx2tf", "backend": "tf_converter", "quantization": "full_integer_quant", "input_dtype": "int8", "output_dtype": "int8", "max_per_model": 1, "only_if": "T1 blocked or host parity fails"},
        ],
        "ort_path": {
            "id": "O1",
            "only_if": "TFLite blocked or TFLite host parity fails",
            "method": "onnxruntime.quantization.quantize_static QDQ per-channel INT8",
            "calibration": "same exact 128 TRAIN membership",
            "max_per_model": 1,
        },
        "fixed_thresholds": {"confidence": 0.25, "nms_iou": 0.70},
        "acceptance": {"count_mismatch_max": 0, "class_mismatch_max": 0, "min_bbox_iou": 0.90, "max_confidence_abs": 0.20},
        "pi_gate": "FULL_INTEGER_INT8 + HOST_PARITY_PASS only",
        "environment": {"venv": str(TFLITE_VENV), "t2_venv": "/tmp/antidrone_scope24_t2_tflite", "project_env_untouched": True},
    }
    (RUNTIME / "tflite_plan.json").write_text(json.dumps(plan, indent=2) + "\n")

    # Scope 23 already materialized the exact calibration tensors.  Only a
    # representation transpose is performed for onnx2tf's NHWC input contract.
    created = []
    for run_id, size in (("scope18-yolov8n-480", 480), ("scope18-yolov8n-640", 640)):
        source = SCOPE23 / "calibration_npy" / "128" / run_id
        files = sorted(source.glob("*.npy"))
        if len(files) != 128:
            raise SystemExit(f"expected 128 tensors for {run_id}, found {len(files)}")
        arrays = [np.load(path).astype(np.float32, copy=False).transpose(1, 2, 0) for path in files]
        batch = np.stack(arrays, axis=0).astype(np.float32, copy=False)
        out = CALIBRATION_DIR / f"{run_id}.npy"
        np.save(out, batch)
        created.append({"run_id": run_id, "size": size, "path": str(out), "shape": list(batch.shape), "dtype": str(batch.dtype), "min": float(batch.min()), "max": float(batch.max()), "mean": float(batch.mean()), "sha256": sha256(out)})
    (RUNTIME / "calibration_nhwc_manifest.json").write_text(json.dumps({"count": 128, "source_split": "train", "test_accessed": False, "records": created}, indent=2) + "\n")


if __name__ == "__main__":
    main()
