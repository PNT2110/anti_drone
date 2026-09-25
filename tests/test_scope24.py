"""Scope 24 freeze and alternate-backend safety guards."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope24"


def read(name):
    return json.loads((RUNTIME / name).read_text())


def test_scope24_only_allows_two_v8_candidates_and_fixed_gates():
    plan = read("tflite_plan.json")
    assert [x["run_id"] for x in plan["candidates"]] == ["scope18-yolov8n-480", "scope18-yolov8n-640"]
    assert plan["fixed_thresholds"] == {"confidence": 0.25, "nms_iou": 0.7}
    assert plan["acceptance"] == {"count_mismatch_max": 0, "class_mismatch_max": 0, "min_bbox_iou": 0.9, "max_confidence_abs": 0.2}
    assert plan["test_access"] is False


def test_scope24_calibration_is_exact_train_only():
    plan = read("tflite_plan.json")
    assert plan["calibration"]["count"] == 128
    assert plan["calibration"]["source_split"] == "train"
    assert plan["calibration"]["manifest_sha256"] == "4c582deab8ec13a23a0ecf0b1b806e6f3dd0c2c43f5a7dca06c785227e444b59"
    assert plan["calibration"]["test_accessed"] is False
    assert read("calibration_nhwc_manifest.json")["test_accessed"] is False


def test_tflite_artifact_audit_and_host_gate_are_not_ready():
    audit = read("tflite_artifact_audit.json")
    assert any(x["status"] == "RUNTIME_INVOKE_BLOCKED" for x in audit["rows"])
    assert any(x["status"] == "FULL_INTEGER_INT8" for x in audit["rows"])
    parity = read("tflite_host_parity.json")
    assert parity["status"] == "TFLITE_HOST_PARITY_FAIL"
    assert parity["test_accessed"] is False
    assert not (RUNTIME / "pi_transfer_manifest.json").exists()


def test_ort_is_one_predeclared_variant_and_blocked():
    plan = read("ort_plan.json")
    assert plan["max_variants_per_model"] == 1
    assert plan["method"]["format"] == "QDQ"
    result = read("ort_host_parity.json")
    assert result["status"] == "ORT_INT8_BLOCKED"
    assert len(result["records"]) == 2


def test_scope24_final_state_preserves_freeze_boundaries():
    final = read("final_summary.json")
    assert final["status"] == "PTQ_INT8_PATHS_EXHAUSTED_FOR_CURRENT_SCOPE"
    assert final["test_accessed"] is False
    assert final["production_freeze"] is False
    assert final["pi_transfer"] is False
