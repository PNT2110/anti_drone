"""Scope 27 frozen detector/tracker dry-run guards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope27"


def read(name: str):
    return json.loads((RUNTIME / name).read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope27_freeze_and_scope26_headline_are_immutable():
    audit = read("input_audit.json")
    assert audit["freeze_manifest_sha256"] == "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
    assert digest(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == audit["freeze_manifest_sha256"]
    assert audit["scope26_headline_sha256"] == "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
    assert digest(ROOT / ".runtime/scope26/headline_result.json") == audit["scope26_headline_sha256"]
    assert audit["v3_test_used_for_tuning"] is False


def test_scope27_detector_contract_and_parity_smoke():
    audit = read("input_audit.json")
    parity = read("parity_smoke.json")
    assert audit["candidate_id"] == "scope18-yolov8n-480:ncnn"
    assert audit["detector"] == {"backend": "NCNN", "precision": "FP32", "imgsz": 480, "confidence": 0.25, "nms_iou": 0.7, "param_sha256": "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5", "bin_sha256": "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"}
    assert parity["status"] == "PARITY_PASS"
    assert len(parity["images"]) == 8
    assert all(row["parity"]["status"] == "PARITY_PASS" for row in parity["images"])


def test_scope27_dryrun_coverage_timestamps_coordinates_and_safety():
    summary = read("dryrun_summary.json")
    rows = [json.loads(line) for line in (RUNTIME / "target_state.jsonl").read_text().splitlines()]
    assert summary["status"] == "DRY_RUN_COMPLETE"
    assert summary["frames_expected"] == 301
    assert summary["frames_processed"] == 301
    assert len(rows) == 301
    assert summary["events"]["COORDINATE_ERROR"]["count"] == 0
    assert summary["events"]["TIMESTAMP_ERROR"]["count"] == 0
    assert summary["actuator"] == {"mode": "DRY_RUN_ONLY", "enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0}
    timestamps = [row["timestamp"] for row in rows]
    assert timestamps == sorted(timestamps)
    assert all(row["command_preview"]["actuator_output_enabled"] is False for row in rows)
    assert all(row["command_preview"]["mode"] == "DRY_RUN_ONLY" for row in rows)


def test_scope27_tracker_profile_and_artifacts_are_present():
    summary = read("dryrun_summary.json")
    assert summary["tracker_profile"] == "bytetrack_motion_adaptive"
    assert summary["track_ids_created"] == [1, 2, 3, 4, 5]
    artifact_manifest = json.loads((ROOT / "artifacts/integration/scope27/ARTIFACT_MANIFEST.json").read_text())
    assert artifact_manifest["status"] == "FROZEN_DETECTOR_TRACKER_DRYRUN_INTEGRATED"
    assert artifact_manifest["actuator_output_enabled"] is False
    assert not (ROOT / "artifacts/integration/scope27/autostart.service").exists()
    for name in ("bytetrack_legacy.yaml", "bytetrack_motion.yaml", "bytetrack_motion_adaptive.yaml"):
        assert (ROOT / "configs/trackers" / name).is_file()
