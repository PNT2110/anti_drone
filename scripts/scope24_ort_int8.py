#!/usr/bin/env python3
"""Bounded Scope 24 ONNX Runtime static INT8 secondary study."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from onnxruntime.quantization import CalibrationDataReader, CalibrationMethod, QuantFormat, QuantType, quantize_static

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope21_pi_runner import decode, iou, preprocess  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope24"
SCOPE19 = ROOT / ".runtime" / "scope19"
SCOPE23 = ROOT / ".runtime" / "scope23"
ACCEPTANCE = {"count_mismatch_max": 0, "class_mismatch_max": 0, "min_bbox_iou": 0.90, "max_confidence_abs": 0.20}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class Reader(CalibrationDataReader):
    def __init__(self, tensors: list[np.ndarray], name: str):
        self.data = iter(({name: x[None].astype(np.float32, copy=False)} for x in tensors))

    def get_next(self):
        return next(self.data, None)


def compare(reference, candidate):
    result = {"reference_count": len(reference), "candidate_count": len(candidate), "count_mismatch": len(reference) != len(candidate), "class_mismatch": False, "min_bbox_iou": 1.0, "max_confidence_abs": 0.0, "status": "PASS"}
    if result["count_mismatch"]:
        result["status"] = "FAIL"
    for left, right in zip(reference, candidate):
        result["class_mismatch"] |= left["class"] != right["class"]
        result["min_bbox_iou"] = min(result["min_bbox_iou"], iou(left["bbox"], right["bbox"]))
        result["max_confidence_abs"] = max(result["max_confidence_abs"], abs(left["confidence"] - right["confidence"]))
    if result["class_mismatch"] or result["min_bbox_iou"] < ACCEPTANCE["min_bbox_iou"] or result["max_confidence_abs"] > ACCEPTANCE["max_confidence_abs"]:
        result["status"] = "FAIL"
    return result


def evaluate(session, paths, size):
    rows = []
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            raise FileNotFoundError(path)
        tensor, gain, pad = preprocess(image, size)
        raw_fp = np.asarray(session[0].run(None, {session[0].get_inputs()[0].name: tensor})[0])
        raw_int = np.asarray(session[1].run(None, {session[1].get_inputs()[0].name: tensor})[0])
        fp_det, fp_contract = decode(raw_fp, gain, pad, image.shape[:2])
        int_det, int_contract = decode(raw_int, gain, pad, image.shape[:2])
        rows.append({"image": path.name, "fp32_detections": fp_det, "ort_int8_detections": int_det, "fp32_contract": fp_contract, "ort_int8_contract": int_contract, "compare": compare(fp_det, int_det)})
    count_mismatch = sum(row["compare"]["count_mismatch"] for row in rows)
    class_mismatch = sum(row["compare"]["class_mismatch"] for row in rows)
    return {"count": len(rows), "count_mismatch": count_mismatch, "class_mismatch": class_mismatch, "minimum_bbox_iou": min(row["compare"]["min_bbox_iou"] for row in rows), "maximum_confidence_abs": max(row["compare"]["max_confidence_abs"] for row in rows), "status": "PASS" if count_mismatch == 0 and class_mismatch == 0 and min(row["compare"]["min_bbox_iou"] for row in rows) >= ACCEPTANCE["min_bbox_iou"] and max(row["compare"]["max_confidence_abs"] for row in rows) <= ACCEPTANCE["max_confidence_abs"] else "FAIL", "rows": rows}


def main() -> int:
    fixed = [Path(p) for p in json.loads((SCOPE19 / "benchmark_input_manifest.json").read_text())["paths"]]
    secondary = [Path(p) for p in json.loads((SCOPE23 / "secondary_diagnostic_manifest.json").read_text())["paths"]]
    records = []
    for run_id, size in (("scope18-yolov8n-480", 480), ("scope18-yolov8n-640", 640)):
        source = ROOT / "artifacts/exports/scope19" / run_id / "float32/onnx/model.onnx"
        out = ROOT / "artifacts/exports/scope24" / run_id / "O1/model_qdq_int8.onnx"
        out.parent.mkdir(parents=True, exist_ok=True)
        row = {"run_id": run_id, "size": size, "status": "ORT_INT8_BLOCKED", "artifact": {"path": str(out)}}
        try:
            tensors = [np.load(path) for path in sorted((SCOPE23 / "calibration_npy/128" / run_id).glob("*.npy"))]
            quantize_static(str(source), str(out), Reader(tensors, "images"), quant_format=QuantFormat.QDQ, calibrate_method=CalibrationMethod.MinMax, activation_type=QuantType.QInt8, weight_type=QuantType.QInt8, per_channel=True, reduce_range=False, extra_options={"ActivationSymmetric": False, "WeightSymmetric": True})
            row["artifact"].update({"sha256": sha256(out), "bytes": out.stat().st_size})
            fp = ort.InferenceSession(str(source), providers=["CPUExecutionProvider"])
            qdq = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
            fixed_result = evaluate((fp, qdq), fixed, size)
            secondary_result = evaluate((fp, qdq), secondary, size)
            row.update({"status": "HOST_PARITY_PASS" if fixed_result["status"] == "PASS" and secondary_result["status"] == "PASS" else "HOST_PARITY_FAIL", "fixed_8": fixed_result, "secondary_32": secondary_result})
        except Exception as exc:
            row["error"] = repr(exc)
        records.append(row)
    result = {"status": "PASS" if all(x["status"] == "HOST_PARITY_PASS" for x in records) else "ORT_INT8_BLOCKED", "acceptance": ACCEPTANCE, "thresholds": {"confidence": 0.25, "nms_iou": 0.70}, "test_accessed": False, "records": records}
    (RUNTIME / "ort_host_parity.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "candidates": [(x["run_id"], x["status"], x.get("fixed_8", {}).get("count_mismatch"), x.get("fixed_8", {}).get("minimum_bbox_iou"), x.get("fixed_8", {}).get("maximum_confidence_abs")) for x in records]}, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
