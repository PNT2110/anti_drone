from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope22"


def test_scope22_allowlist_and_calibration_are_locked():
    audit = json.loads((RUNTIME / "input_audit.json").read_text())
    assert audit["status"] == "PASS"
    assert audit["approved_candidates"] == [
        "scope18-yolov8n-480:ncnn",
        "scope18-yolov8n-640:ncnn",
        "scope18-yolov11n-480:ncnn",
    ]
    assert not any("yolo26" in x for x in audit["approved_candidates"])
    assert audit["calibration_manifest"]["count"] == 128
    assert audit["calibration_manifest"]["source_split"] == "train"
    assert audit["calibration_manifest"]["test_accessed"] is False


def test_scope22_exports_have_quantization_evidence_but_are_not_ready():
    exports = json.loads((RUNTIME / "int8_export.json").read_text())
    assert exports["status"] == "PASS"
    assert len(exports["candidates"]) == 3
    for row in exports["candidates"]:
        assert row["status"] == "INT8_RUNTIME_CANDIDATE"
        assert row["ncnn2table"]["returncode"] == 0
        assert row["ncnn2int8"]["returncode"] == 0
        assert row["artifact"]["int8_param_markers_8_eq_1_or_2"] > 0


def test_scope22_host_gate_blocks_pi_and_keeps_test_closed():
    parity = json.loads((RUNTIME / "host_int8_parity.json").read_text())
    pi = json.loads((RUNTIME / "pi_int8_benchmark.json").read_text())
    assert parity["status"] == "INT8_RUNTIME_FAIL"
    assert all(row["detection_count_mismatch"] > 0 for row in parity["records"])
    assert pi["status"] == "INT8_PATH_BLOCKED"
    assert pi["results"] == []
    assert pi["test_accessed"] is False
