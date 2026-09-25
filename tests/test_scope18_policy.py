"""Regression guards for the Scope 18 controlled-training contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.scope18_policy import output_is_safe, training_data_policy, validate_resume


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs/training/scope18"


def _resume_pair() -> tuple[dict, dict]:
    values = {
        "run_id": "scope18-yolov8n-640",
        "model_id": "yolov8n",
        "imgsz": 640,
        "dataset_manifest_sha256": "manifest",
        "dataset_split_registry_sha256": "registry",
        "seed": 42,
        "effective_batch": 16,
    }
    return dict(values), dict(values)


def test_resume_requires_exact_identity_contract():
    requested, checkpoint = _resume_pair()
    assert validate_resume(requested, checkpoint) == (True, "resume contract matched")
    checkpoint["imgsz"] = 480
    assert validate_resume(requested, checkpoint)[0] is False


def test_best_checkpoint_cannot_be_used_as_resume_source():
    requested, checkpoint = _resume_pair()
    requested["checkpoint_kind"] = "best.pt"
    assert validate_resume(requested, checkpoint)[0] is False


def test_training_policy_locks_test_split():
    policy = training_data_policy()
    assert policy["allowed_splits"] == ["train", "val"]
    assert policy["test_allowed"] is False
    assert policy["test_selection"] is False
    assert policy["test_scoring"] is False


def test_scope18_output_root_cannot_alias_older_scopes():
    scope18 = str(ROOT / "artifacts/experiments/scope18-v3-labelrepair")
    assert output_is_safe(scope18, str(ROOT / "artifacts/experiments/scope15-v3"), str(ROOT / "artifacts/experiments/scope16-v3"))
    assert not output_is_safe(str(ROOT / "artifacts/experiments/scope15-v3"), str(ROOT / "artifacts/experiments/scope15-v3"), str(ROOT / "artifacts/experiments/scope16-v3"))
    assert not output_is_safe(str(ROOT / "artifacts/experiments/scope16-v3"), str(ROOT / "artifacts/experiments/scope15-v3"), str(ROOT / "artifacts/experiments/scope16-v3"))


def test_six_configs_use_repaired_candidate_and_lock_test():
    configs = sorted(CONFIG_DIR.glob("scope18-*.json"))
    assert len(configs) == 6
    for path in configs:
        config = json.loads(path.read_text(encoding="utf-8"))
        assert "drone-single-class-v3-labelrepair-candidate" in config["data"]
        assert config["validation_policy"] == "V3 val only; no V3 test read for selection"
        assert config["test_policy"].startswith("locked")
        assert config["training_not_run"] is True
        assert config["batch_fallback_policy"] == [16, 8, 4]
        assert config["seed"] == 42


def test_label_preflight_artifact_is_pass_and_complete():
    artifact = ROOT / ".runtime/scope18/label_preflight.json"
    if not artifact.exists():
        pytest.fail("Scope 18 label preflight artifact is missing")
    report = json.loads(artifact.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["sample_count"] == 30227
    assert report["split_counts"] == {"test": 9848, "train": 12142, "val": 8237}
    assert report["empty_label_count"] == 0
    assert report["source_unresolved_count"] == 0
    assert report["quarantine_leakage"] == 0
