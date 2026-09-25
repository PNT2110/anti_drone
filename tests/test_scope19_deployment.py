import json
from pathlib import Path

from scripts.scope19_deployment import EXPECTED_BEST, OUTPUT, TOLERANCE, compare_detections, validate_output_path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope19"


def read_json(name):
    return json.loads((RUNTIME / name).read_text(encoding="utf-8"))


def test_scope19_input_audit_freezes_all_scope18_checkpoints_and_test_lock():
    audit = read_json("input_audit.json")
    assert audit["status"] == "PASS"
    assert audit["test_accessed"] is False
    assert set(audit["checkpoints"]) == set(EXPECTED_BEST)
    assert all(row["match"] and row["scope18_status"] == "COMPLETE" for row in audit["checkpoints"].values())


def test_scope19_benchmark_and_calibration_are_train_only():
    benchmark = read_json("benchmark_input_manifest.json")
    calibration = read_json("calibration_manifest.json")
    assert benchmark["split"] == "train"
    assert benchmark["test_accessed"] is False
    assert calibration["source_split"] == "train"
    assert calibration["test_accessed"] is False
    assert calibration["count"] == 128


def test_scope19_parity_policy_rejects_confidence_and_bbox_drift():
    reference = [{"class": 0, "confidence": 0.8, "bbox": [0, 0, 10, 10]}]
    assert compare_detections(reference, reference)["status"] == "PASS"
    confidence_drift = [{"class": 0, "confidence": 0.8 + TOLERANCE["confidence_abs"] + 0.001, "bbox": [0, 0, 10, 10]}]
    assert compare_detections(reference, confidence_drift)["status"] == "BACKEND_PARITY_FAIL"
    bbox_drift = [{"class": 0, "confidence": 0.8, "bbox": [4, 0, 14, 10]}]
    assert compare_detections(reference, bbox_drift)["status"] == "BACKEND_PARITY_FAIL"


def test_scope19_export_path_cannot_overwrite_checkpoint():
    checkpoint = ROOT / "artifacts/experiments/scope18-v3-labelrepair/scope18-yolov8n-640/attempt-batch16/weights/best.pt"
    assert not validate_output_path(checkpoint, checkpoint)
    assert validate_output_path(OUTPUT / "scope18-yolov8n-640" / "float32" / "onnx", checkpoint)


def test_scope19_blocked_formats_are_not_reported_as_exported():
    report = read_json("export_report.json")
    assert all(item["status"] != "EXPORTED" for item in report["int8"])
    tflite = [item for item in report["exports"] if item["runtime"] == "tflite"]
    assert len(tflite) == 6
    assert all(item["status"] == "BLOCKED" for item in tflite)
