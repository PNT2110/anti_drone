"""Scope 29 live-camera safety and baseline guards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope29"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name: str):
    return json.loads((RUNTIME / name).read_text())


def test_scope29_frozen_baselines_are_unchanged():
    assert digest(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
    assert digest(ROOT / ".runtime/scope26/headline_result.json") == "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
    assert digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
    assert digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def test_scope29_pre_live_parity_and_contract():
    parity = read("parity_8.json")
    audit = read("input_audit.json")
    assert parity["status"] == "PARITY_PASS"
    assert len(parity["images"]) == 8
    assert all(row["comparison"]["status"] == "PARITY_PASS" for row in parity["images"])
    assert all(row["contract"]["nms_applications"] == 1 for row in parity["images"])
    assert audit["detector"]["public_confidence"] == 0.25
    assert audit["detector"]["tracker_floor"] == 0.10
    assert audit["detector"]["nms_iou"] == 0.70
    assert audit["tracker_profile"] == "bytetrack_motion_adaptive"


def test_scope29_invalid_camera_is_safe_and_final_status_is_not_fake_pass():
    invalid = read("invalid_camera_summary.json")
    final = read("scope29_final_status.json")
    assert invalid["status"] == "CAMERA_OPEN_FAILED"
    assert invalid["model_loaded"] is False
    assert invalid["actuator"]["enabled"] is False
    assert final["status"] == "CAMERA_RUNTIME_BLOCKED"
    assert final["actuator_output_enabled"] is False
    assert final["v3_test_accessed"] is False


def test_scope29_runner_has_bounded_queue_and_no_autostart_or_actuator_imports():
    source = (ROOT / "scripts/scope29_pi_live.py").read_text()
    assert "Queue(maxsize=1)" in source
    assert "drop_stale_keep_newest" in source
    assert "DRY_RUN_ONLY" in source
    assert "GPIO" not in source and "PWM" not in source and "serial.Serial" not in source
    assert not (ROOT / "artifacts/integration/scope29/autostart.service").exists()
