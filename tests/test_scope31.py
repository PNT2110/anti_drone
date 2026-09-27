"""Scope 31 mandatory power-gate and no-actuation guards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope31_frozen_baselines_and_power_gate():
    assert sha(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
    assert sha(ROOT / ".runtime/scope26/headline_result.json") == "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
    assert sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
    assert sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"
    status = json.loads((ROOT / ".runtime/scope31/final_status.json").read_text())
    assert status["status"] == "PAN_NEUTRAL_COMMISSIONING_BLOCKED"
    assert status["gate"]["voltage_verified"] is False
    assert status["gate"]["pwm_initialized"] is True
    assert status["gate"]["gpio_initialized"] is True
    assert status["resume"]["power_status"] == "POWER_VOLTAGE_UNMEASURED_USER_ACCEPTED"
    assert status["resume"]["pan_center_command"]["observed_result"] == "NO_RESPONSE"


def test_scope31_mapping_is_recorded_without_actuation():
    contract = (ROOT / "docs/tracking/scope31/SCOPE31_MG90S_HARDWARE_CONTRACT.md").read_text()
    final = json.loads((ROOT / ".runtime/scope31/final_status.json").read_text())
    assert "BCM GPIO13" in contract and "BCM GPIO12" in contract
    assert final["hardware"]["pan_gpio"] == "BCM GPIO13"
    assert final["hardware"]["tilt_gpio"] == "BCM GPIO12"
    assert final["gate"]["physical_movement_attempted"] is True
    assert final["gate"]["pwm_writes"] == 1
    assert final["gate"]["serial_writes"] == 0
    assert final["gate"]["motor_writes"] == 0
    assert final["gate"]["v3_test_accessed"] is False


def test_scope31_does_not_enable_autostart_or_ai_servo_path():
    assert not (ROOT / "artifacts/integration/scope31/autostart.service").exists()
    final = json.loads((ROOT / ".runtime/scope31/final_status.json").read_text())
    assert final["gate"]["ai_to_servo_connected"] is False
    report = (ROOT / "docs/tracking/scope31/SCOPE31_FINAL_REPORT.md").read_text()
    assert "PAN_NEUTRAL_COMMISSIONING_BLOCKED" in report
    assert "POWER_VOLTAGE_UNMEASURED_USER_ACCEPTED" in report
