"""Regression guards for the bounded Scope 23 PTQ study."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope23"


def load(name: str):
    return json.loads((RUNTIME / name).read_text())


def test_scope23_plan_is_frozen_and_bounded():
    plan = load("experiment_plan.json")
    assert plan["status"] == "FROZEN_BEFORE_RESULTS"
    assert plan["no_test"] is True
    assert plan["max_configurations_per_primary"] == 4
    assert plan["fixed_thresholds"] == {"confidence": 0.25, "nms_iou": 0.7}
    assert plan["primary_candidates"] == [
        "scope18-yolov8n-640:ncnn",
        "scope18-yolov8n-480:ncnn",
    ]
    assert plan["secondary_confirmation"] == "scope18-yolov11n-480:ncnn only after a v8 method passes"


def test_scope23_calibration_and_diagnostics_are_train_only():
    plan = load("experiment_plan.json")
    assert plan["diagnostic_sets"]["fixed_8"]["split"] == "train"
    assert plan["diagnostic_sets"]["fixed_8"]["test_accessed"] is False
    secondary = load("secondary_diagnostic_manifest.json")
    assert secondary["count"] == 32
    assert secondary["source_split"] == "train"
    assert secondary["test_accessed"] is False
    for path in (RUNTIME / "calibration_manifests").glob("*.json"):
        manifest = json.loads(path.read_text())
        assert manifest["source_split"] == "train"
        assert manifest["test_accessed"] is False
        assert manifest["count"] in (128, 256)


def test_scope23_only_declared_experiments_have_results():
    plan = load("experiment_plan.json")
    declared = {item["id"] for item in plan["experiments"] if not item.get("scope22_baseline")}
    actual = {p.parent.name for p in (RUNTIME / "experiments").glob("*/host_results.json")}
    assert actual == declared - {"E0"}
    for experiment in sorted(actual):
        result = load(f"experiments/{experiment}/host_results.json")
        assert result["thresholds"] == {"confidence": 0.25, "nms_iou": 0.7}
        assert result["test_accessed"] is False


def test_host_failure_cannot_be_ready():
    summary = load("experiment_summary.json")
    assert summary["status"] == "NCNN_INT8_PTQ_BLOCKED"
    assert all(item["status"] == "FAIL" for item in summary["experiments"])
    assert not (RUNTIME / "pi_transfer_manifest.json").exists()
