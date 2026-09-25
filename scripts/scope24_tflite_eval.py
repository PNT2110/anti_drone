#!/usr/bin/env python3
"""Audit and evaluate Scope 24 T1 full-integer TFLite artifacts on host."""
from __future__ import annotations

import hashlib
import json
import sys
import argparse
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope21_pi_runner import decode, iou, preprocess  # noqa: E402

try:
    from ai_edge_litert.interpreter import Interpreter, OpResolverType
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"LiteRT unavailable: {exc}")


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


def tensor_meta(detail: dict) -> dict:
    q = detail["quantization_parameters"]
    return {
        "name": detail["name"],
        "shape": detail["shape"].tolist(),
        "dtype": np.dtype(detail["dtype"]).name,
        "quantization": [float(detail["quantization"][0]), int(detail["quantization"][1])],
        "scales": np.asarray(q["scales"]).astype(float).tolist(),
        "zero_points": np.asarray(q["zero_points"]).astype(int).tolist(),
        "quantized_dimension": int(q["quantized_dimension"]),
    }


def load_tflite(path: Path):
    interpreter = Interpreter(model_path=str(path), experimental_op_resolver_type=OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES)
    interpreter.allocate_tensors()
    inputs = interpreter.get_input_details()
    outputs = interpreter.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError(f"unexpected tensor count: {len(inputs)} inputs, {len(outputs)} outputs")
    return interpreter, inputs[0], outputs[0]


def run_tflite(interpreter, input_detail, output_detail, image, size):
    tensor, gain, pad = preprocess(image, size)
    nhwc = np.ascontiguousarray(tensor.transpose(0, 2, 3, 1))
    scale, zero = input_detail["quantization"]
    if np.dtype(input_detail["dtype"]).kind in "iu":
        if not scale:
            raise RuntimeError("quantized input has zero scale")
        model_input = np.rint(nhwc / scale + zero).clip(np.iinfo(input_detail["dtype"]).min, np.iinfo(input_detail["dtype"]).max).astype(input_detail["dtype"])
    else:
        model_input = nhwc.astype(input_detail["dtype"])
    interpreter.set_tensor(input_detail["index"], model_input)
    interpreter.invoke()
    raw = interpreter.get_tensor(output_detail["index"])
    out_scale, out_zero = output_detail["quantization"]
    if np.dtype(output_detail["dtype"]).kind in "iu":
        raw = (raw.astype(np.float32) - out_zero) * out_scale
    detections, contract = decode(raw, gain, pad, image.shape[:2])
    return detections, contract, {"input_stats": {"dtype": str(model_input.dtype), "shape": list(model_input.shape), "min": int(model_input.min()), "max": int(model_input.max()), "mean": float(model_input.mean()), "scale": float(scale), "zero_point": int(zero)}, "output_stats": {"dtype": str(output_detail["dtype"]), "shape": list(raw.shape), "min": float(raw.min()), "max": float(raw.max()), "mean": float(raw.mean()), "scale": float(out_scale), "zero_point": int(out_zero)}}


def run_onnx(session, image, size):
    tensor, gain, pad = preprocess(image, size)
    raw = np.asarray(session.run(None, {session.get_inputs()[0].name: tensor})[0])
    detections, contract = decode(raw, gain, pad, image.shape[:2])
    return detections, contract


def compare(reference, candidate):
    result = {"reference_count": len(reference), "candidate_count": len(candidate), "count_mismatch": len(reference) != len(candidate), "class_mismatch": False, "min_bbox_iou": 1.0, "max_confidence_abs": 0.0, "status": "PASS"}
    if len(reference) != len(candidate):
        result["status"] = "FAIL"
    for left, right in zip(reference, candidate):
        result["class_mismatch"] = result["class_mismatch"] or left["class"] != right["class"]
        result["min_bbox_iou"] = min(result["min_bbox_iou"], iou(left["bbox"], right["bbox"]))
        result["max_confidence_abs"] = max(result["max_confidence_abs"], abs(left["confidence"] - right["confidence"]))
    if result["class_mismatch"] or result["min_bbox_iou"] < ACCEPTANCE["min_bbox_iou"] or result["max_confidence_abs"] > ACCEPTANCE["max_confidence_abs"]:
        result["status"] = "FAIL"
    return result


def evaluate_set(session, interpreter, inp, out, paths, size):
    rows = []
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            raise FileNotFoundError(path)
        fp_det, fp_contract = run_onnx(session, image, size)
        int_det, int_contract, quant_stats = run_tflite(interpreter, inp, out, image, size)
        rows.append({"image": path.name, "fp32_detections": fp_det, "tflite_detections": int_det, "fp32_contract": fp_contract, "tflite_contract": int_contract, "quantization": quant_stats, "compare": compare(fp_det, int_det)})
    count_mismatch = sum(row["compare"]["count_mismatch"] for row in rows)
    class_mismatch = sum(row["compare"]["class_mismatch"] for row in rows)
    result = {"count": len(rows), "count_mismatch": count_mismatch, "class_mismatch": class_mismatch, "minimum_bbox_iou": min(row["compare"]["min_bbox_iou"] for row in rows), "maximum_confidence_abs": max(row["compare"]["max_confidence_abs"] for row in rows), "status": "PASS" if count_mismatch <= ACCEPTANCE["count_mismatch_max"] and class_mismatch <= ACCEPTANCE["class_mismatch_max"] and result_min(rows) >= ACCEPTANCE["min_bbox_iou"] and result_max(rows) <= ACCEPTANCE["max_confidence_abs"] else "FAIL", "rows": rows}
    return result


def result_min(rows):
    return min(row["compare"]["min_bbox_iou"] for row in rows)


def result_max(rows):
    return max(row["compare"]["max_confidence_abs"] for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("T1", "T2"), default="T1")
    parser.add_argument("--run-id", choices=("scope18-yolov8n-480", "scope18-yolov8n-640"))
    args = parser.parse_args()
    fixed = [Path(p) for p in json.loads((SCOPE19 / "benchmark_input_manifest.json").read_text())["paths"]]
    secondary = [Path(p) for p in json.loads((SCOPE23 / "secondary_diagnostic_manifest.json").read_text())["paths"]]
    records = []
    for run_id, size in (("scope18-yolov8n-480", 480), ("scope18-yolov8n-640", 640)):
        if args.run_id and run_id != args.run_id:
            continue
        model = ROOT / "artifacts/exports/scope24" / run_id / args.variant / "model_full_integer_quant.tflite"
        if not model.exists():
            records.append({"run_id": run_id, "size": size, "status": "EXECUTION_BLOCKED", "reason": f"missing {args.variant} full-integer artifact"})
            continue
        session = ort.InferenceSession(str(ROOT / "artifacts/exports/scope19" / run_id / "float32/onnx/model.onnx"), providers=["CPUExecutionProvider"])
        interpreter, inp, out = load_tflite(model)
        fixed_result = evaluate_set(session, interpreter, inp, out, fixed, size)
        secondary_result = evaluate_set(session, interpreter, inp, out, secondary, size)
        metadata = {"model": str(model), "sha256": sha256(model), "bytes": model.stat().st_size, "input": tensor_meta(inp), "output": tensor_meta(out), "ops": sorted({x["op_name"] for x in interpreter._get_ops_details()}), "runtime": "ai-edge-litert", "default_delegates_disabled": True}
        status = "HOST_PARITY_PASS" if fixed_result["status"] == "PASS" and secondary_result["status"] == "PASS" else "HOST_PARITY_FAIL"
        records.append({"run_id": run_id, "size": size, "status": status, "metadata": metadata, "fixed_8": fixed_result, "secondary_32": secondary_result})
    result = {"variant": args.variant, "status": "PASS" if all(x["status"] == "HOST_PARITY_PASS" for x in records) else "TFLITE_HOST_PARITY_FAIL", "acceptance": ACCEPTANCE, "thresholds": {"confidence": 0.25, "nms_iou": 0.70}, "test_accessed": False, "records": records}
    (RUNTIME / "tflite_host_parity.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "candidates": [(x["run_id"], x["status"], x["fixed_8"]["count_mismatch"], x["fixed_8"]["minimum_bbox_iou"], x["fixed_8"]["maximum_confidence_abs"]) for x in records]}, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
