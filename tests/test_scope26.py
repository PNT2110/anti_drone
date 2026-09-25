"""Scope 26 guards for the one-time frozen NCNN TEST evaluation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope26"
FREEZE_HASH = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"


def read(name: str):
    return json.loads((RUNTIME / name).read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope26_freeze_and_candidate_are_exact():
    freeze_path = ROOT / ".runtime/scope25/scope25_freeze_manifest.json"
    freeze = json.loads(freeze_path.read_text())
    assert digest(freeze_path) == FREEZE_HASH
    assert freeze["status"] == "FP32_NCNN_CANDIDATE_FROZEN"
    assert freeze["candidate_id"] == "scope18-yolov8n-480:ncnn"
    assert freeze["ncnn_param_sha256"] == "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
    assert freeze["ncnn_bin_sha256"] == "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"
    assert freeze["test_accessed"] is False


def test_scope26_open_event_keeps_frozen_contract_and_split():
    event = read("test_open_event.json")
    assert event["freeze_manifest_sha256"] == FREEZE_HASH
    assert event["candidate_id"] == "scope18-yolov8n-480:ncnn"
    assert event["backend"] == "NCNN"
    assert event["precision"] == "FP32"
    assert event["imgsz"] == 480
    assert event["confidence"] == 0.25
    assert event["nms_iou"] == 0.70
    assert event["expected_test_images"] == 9848
    assert event["test_open_authorized"] is True


def test_scope26_coverage_and_headline_are_immutable():
    runner = read("pi_runner_result.json")
    headline = read("headline_result.json")
    audit = read("metric_audit.json")
    assert runner["status"] == "FINAL_TEST_COMPLETE"
    assert runner["processed"] == 9848
    assert runner["skipped"] == 0
    assert headline["processed_samples"] == 9848
    assert headline["expected_samples"] == 9848
    assert headline["skipped_samples"] == 0
    assert headline["candidate_id"] == "scope18-yolov8n-480:ncnn"
    assert digest(RUNTIME / "headline_result.json") == (RUNTIME / "headline_result.sha256").read_text().split()[0]
    assert audit["no_pytorch_primary"] is True
    assert audit["no_threshold_sweep"] is True
    assert audit["no_model_switch"] is True


def test_scope26_package_and_tracker_boundaries():
    package = ROOT / "artifacts/production-candidate/scope25"
    assert (package / "model.ncnn.param").is_file()
    assert (package / "model.ncnn.bin").is_file()
    assert (package / "SHA256SUMS").is_file()
    assert not (ROOT / "artifacts/production-candidate/scope26").exists()
    for name in ("bytetrack_legacy.yaml", "bytetrack_motion.yaml", "bytetrack_motion_adaptive.yaml"):
        assert (ROOT / "configs/trackers" / name).is_file()
