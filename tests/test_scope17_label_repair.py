"""Regression guards for the Scope 17 source-annotation repair artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_and_repair_baselines_are_distinct_and_locked():
    assert sha256(ROOT / "data/processed/drone-single-class-v3-candidate/manifest.json") == "b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc"
    assert sha256(ROOT / "data/processed/drone-single-class-v3-candidate/split_registry.json") == "57ffb56effd35ad65aad9d163e586ebd8c9f9f1f19c93a86d5fd7619d72cff3d"
    assert sha256(ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate/manifest.json") != sha256(ROOT / "data/processed/drone-single-class-v3-candidate/manifest.json")


def test_coordinate_contract_is_xywh_zero_based_direct_image_space():
    rect = [747.0, 489.0, 53.0, 41.0]
    width, height = 1920, 1080
    converted = [(rect[0] + rect[2] / 2) / width, (rect[1] + rect[3] / 2) / height, rect[2] / width, rect[3] / height]
    assert converted == pytest.approx([0.4028645833333333, 0.47175925925925925, 0.027604166666666668, 0.03796296296296296], abs=1e-12)


def test_scope17_audit_proves_all_source_objects_repaired():
    audit = json.loads((ROOT / ".runtime/scope17/label_repair_audit.json").read_text(encoding="utf-8"))
    assert audit["status"] == "PASS"
    assert audit["source_object_count"] == 30227
    assert audit["source_confirmed_negative_count"] == 0
    assert audit["source_annotation_unresolved_count"] == 0
    assert audit["object_count"] == 30227
    assert audit["repair_status_counts"] == {"REPAIRED_FROM_SOURCE_ANNOTATION": 30227}


def test_scope17_preserves_split_and_quarantine_contract():
    audit = json.loads((ROOT / ".runtime/scope17/label_repair_audit.json").read_text(encoding="utf-8"))
    assert audit["split_counts"] == {"test": 9848, "train": 12142, "val": 8237}
    assert audit["source_sequence_overlap"] == 0
    assert audit["candidate_prefix_overlap"] == 0
    assert audit["quarantine_leakage"] == 0


def test_scope16_training_was_not_started():
    assert not (ROOT / "artifacts/experiments/scope16-v3").exists()
    matrix = json.loads((ROOT / ".runtime/scope16/training_matrix.json").read_text(encoding="utf-8"))
    assert matrix["training_started"] is False
    assert all(run["status"] == "NOT_STARTED_LABEL_PREFLIGHT" for run in matrix["runs"])
