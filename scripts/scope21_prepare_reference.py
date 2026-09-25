#!/usr/bin/env python3
"""Create fixed host PyTorch references for Scope 21 Pi runtime parity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from scope20_parity import ORDER, checkpoint_path, final_detections, load, tensor_from_output
from ultralytics.models.yolo.detect.predict import DetectionPredictor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".runtime/scope21/host_reference.json"


def tensor_stats(array: np.ndarray) -> dict:
    values = np.ascontiguousarray(array)
    return {"shape": list(values.shape), "dtype": str(values.dtype), "min": float(values.min()), "max": float(values.max()), "mean": float(values.mean()), "sha256": hashlib.sha256(values.tobytes()).hexdigest()}


def main() -> int:
    manifest = load("benchmark_input_manifest.json")
    records = []
    for model_id, imgsz in ORDER:
        run_id = f"scope18-{model_id}-{imgsz}"
        predictor = DetectionPredictor(overrides={"imgsz": imgsz, "conf": 0.25, "iou": 0.70, "device": "cpu", "verbose": False, "rect": False})
        predictor.setup_model(str(checkpoint_path(run_id)), verbose=False)
        predictor.imgsz = (imgsz, imgsz)
        for image_path in manifest["paths"]:
            image = cv2.imread(image_path)
            if image is None:
                raise FileNotFoundError(image_path)
            pre = predictor.preprocess([image])
            raw = tensor_from_output(predictor.model(pre))
            raw_np = raw.detach().float().cpu().numpy()
            if raw_np.shape[1] == 5:
                contract = {"raw_shape": list(raw_np.shape), "xywh": True, "nms_embedded": False, "nms_applications": 1}
            elif raw_np.ndim == 3 and raw_np.shape[2] == 6:
                contract = {"raw_shape": list(raw_np.shape), "xywh": False, "nms_embedded": True, "nms_applications": 0}
            else:
                raise ValueError(f"unexpected host output shape {raw_np.shape}")
            records.append({"run_id": run_id, "image": Path(image_path).name, "imgsz": imgsz, "preprocess": tensor_stats(pre.detach().cpu().numpy()), "contract": contract, "detections": final_detections(raw, pre.shape[2:], image.shape)})
    OUT.write_text(json.dumps({"status": "PASS", "split": manifest["split"], "test_accessed": False, "image_count": len(manifest["paths"]), "records": records}, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "records": len(records), "path": str(OUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
