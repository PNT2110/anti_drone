"""Scope 30R alignment-stop and servo-identification guards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope30r"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope30r_baselines_and_alignment_stop():
    assert digest(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
    assert digest(ROOT / ".runtime/scope26/headline_result.json") == "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
    assert digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
    assert digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"
    final = json.loads((RUNTIME / "final_status.json").read_text())
    assert final["status"] == "TARGET_ALIGNMENT_REQUIRED"
    assert final["alignment"]["monitor_visible"] is False
    assert final["alignment"]["video_visible"] is False
    assert final["accepted_target_session_started"] is False
    assert final["test_accessed"] is False
    assert final["no_gpio_pwm_serial_servo_motor_writes"] is True


def test_scope30r_snapshot_exists_and_is_not_a_fake_target_run():
    assert (RUNTIME / "target_alignment_snapshot.jpg").exists()
    assert not (RUNTIME / "target_summary.json").exists()
    assert "TARGET_ALIGNMENT_REQUIRED" in (ROOT / "docs/tracking/scope30/SCOPE30_TARGET_ALIGNMENT.md").read_text()


def test_scope30r_missing_servo_evidence_is_explicit():
    report = (ROOT / "docs/tracking/scope30/SCOPE30R_SERVO_INFORMATION_REQUIRED.md").read_text()
    for required in ("pan actuator", "tilt actuator", "controller board", "channel mapping", "power", "safe neutral"):
        assert required in report
    assert "SERVO_BOUNDS_UNKNOWN" in report
