#!/usr/bin/env python3
"""Validate Scope 22 NCNN INT8 artifacts against host FP32 NCNN."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope21_pi_runner import compare, infer, load_runtime  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope22"
SCOPE19 = ROOT / ".runtime/scope19"
APPROVED = [("scope18-yolov8n-480", 480), ("scope18-yolov8n-640", 640), ("scope18-yolov11n-480", 480)]
ACCEPTANCE = {"bbox_iou_min": 0.90, "confidence_abs_max": 0.20, "detection_count_mismatch_max": 0, "class_mismatch_max": 0}


def main() -> int:
    manifest = json.loads((SCOPE19 / "benchmark_input_manifest.json").read_text())
    exports = json.loads((RUNTIME / "int8_export.json").read_text())
    exp_by_id = {x["run_id"]: x for x in exports["candidates"]}
    records = []
    for run_id, size in APPROVED:
        fp_root = ROOT / "artifacts/exports/scope19" / run_id / "float32/ncnn/model_ncnn_model"
        int8_root = Path(exp_by_id[run_id]["artifact"]["param"]).parent
        fp_candidate = {"backend": "ncnn", "artifact_path": str(fp_root), "threads": 4}
        int_candidate = {"backend": "ncnn", "artifact_path": str(int8_root), "threads": 4}
        fp_runtime, fp_meta = load_runtime(fp_candidate)
        int_runtime, int_meta = load_runtime(int_candidate)
        image_rows = []
        for image_path in manifest["paths"]:
            image = cv2.imread(image_path)
            fp_det, fp_contract, _ = infer(fp_runtime, fp_candidate, image, size)
            int_det, int_contract, _ = infer(int_runtime, int_candidate, image, size)
            cmp = compare(fp_det, int_det)
            image_rows.append({"image": Path(image_path).name, "fp32_detections": fp_det, "int8_detections": int_det, "fp32_contract": fp_contract, "int8_contract": int_contract, "compare": cmp})
        count_mismatch = sum(x["compare"]["reference_count"] != x["compare"]["candidate_count"] for x in image_rows)
        class_mismatch = sum(not x["compare"]["class_exact"] for x in image_rows)
        min_iou = min(x["compare"]["min_bbox_iou"] for x in image_rows)
        max_conf = max(x["compare"]["max_confidence_abs"] for x in image_rows)
        status = "HOST_INT8_RUNTIME_PASS"
        if count_mismatch > ACCEPTANCE["detection_count_mismatch_max"] or class_mismatch > ACCEPTANCE["class_mismatch_max"] or min_iou < ACCEPTANCE["bbox_iou_min"] or max_conf > ACCEPTANCE["confidence_abs_max"]:
            status = "INT8_RUNTIME_FAIL"
        records.append({"run_id": run_id, "size": size, "status": status, "fp32_runtime": fp_meta, "int8_runtime": int_meta, "acceptance": ACCEPTANCE, "detection_count_mismatch": count_mismatch, "class_mismatch": class_mismatch, "minimum_bbox_iou": min_iou, "maximum_confidence_abs": max_conf, "images": image_rows})
    result = {"status": "PASS" if all(x["status"] == "HOST_INT8_RUNTIME_PASS" for x in records) else "INT8_RUNTIME_FAIL", "acceptance": ACCEPTANCE, "records": records, "split": manifest["split"], "test_accessed": False}
    (RUNTIME / "host_int8_parity.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "candidates": [(x["run_id"], x["status"], x["minimum_bbox_iou"], x["maximum_confidence_abs"], x["detection_count_mismatch"], x["class_mismatch"]) for x in records]}, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
