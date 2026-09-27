"""Scope 30R2 fresh-snapshot alignment gate guards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope30r2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope30r2_baselines_and_attempt_history():
    assert sha(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
    assert sha(ROOT / ".runtime/scope26/headline_result.json") == "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
    assert sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
    assert sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"
    final = json.loads((RUNTIME / "final_status.json").read_text())
    assert final["attempt"] == 3
    assert final["history"] == {"attempt_1": "LIVE_TARGET_TRACKING_BLOCKED", "attempt_2": "TARGET_ALIGNMENT_REQUIRED", "attempt_3": "TARGET_ALIGNMENT_REQUIRED"}
    assert final["status"] == "TARGET_ALIGNMENT_REQUIRED"


def test_scope30r2_fresh_snapshot_is_alignment_blocked():
    final = json.loads((RUNTIME / "final_status.json").read_text())
    snapshot = RUNTIME / "target_alignment_snapshot.jpg"
    assert snapshot.exists()
    assert final["alignment"]["snapshot_sha256"] == sha(snapshot)
    assert final["alignment"]["monitor_visible"] is False
    assert final["alignment"]["video_visible"] is False
    assert final["accepted_target_session_started"] is False
    assert not (RUNTIME / "target_summary.json").exists()


def test_scope30r2_dryrun_and_test_safety():
    final = json.loads((RUNTIME / "final_status.json").read_text())
    assert final["no_gpio_pwm_serial_servo_motor_writes"] is True
    assert final["test_accessed"] is False
    assert final["servo_status"] == "PHYSICAL_SERVO_COMMISSIONING_BLOCKED_BY_UNKNOWN_BOUNDS"


def test_scope30r2_attempt4_live_target_acceptance():
    runtime = RUNTIME / "attempt4"
    summary = json.loads((runtime / "target_summary.json").read_text())
    final = json.loads((runtime / "final_status.json").read_text())
    assert final["status"] == "LIVE_TARGET_COMMAND_PREVIEW_READY"
    assert summary["status"] == "LIVE_TARGET_RUN_COMPLETE"
    assert summary["target_seen"] is True
    assert summary["frames_dropped"]["capture_read_failures"] == 0
    assert summary["frames_dropped"]["invalid_frame_dimensions"] == 0
    assert summary["counts"]["high_detection_frames"] > 0
    assert summary["counts"]["low_only_detection_frames"] > 0
    assert summary["track_ids_created"]
    assert final["command_preview"]["non_neutral_samples"] > 0
    assert final["command_preview"]["loss_to_neutral_observed"] is True
    assert summary["actuator"]["enabled"] is False
    assert summary["actuator"]["gpio_writes"] == 0
    assert summary["actuator"]["pwm_writes"] == 0
    assert summary["actuator"]["serial_writes"] == 0
    assert summary["actuator"]["servo_writes"] == 0
    assert summary["actuator"]["motor_writes"] == 0
