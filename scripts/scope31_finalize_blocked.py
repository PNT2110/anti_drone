#!/usr/bin/env python3
"""Record the Scope 31 mandatory power-gate blocker without hardware access."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope31"
ARTIFACTS = ROOT / "artifacts/integration/scope31"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    expected = {
        "freeze_manifest": "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964",
        "scope26_headline": "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83",
        "param": "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5",
        "bin": "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7",
    }
    actual = {
        "freeze_manifest": sha(ROOT / ".runtime/scope25/scope25_freeze_manifest.json"),
        "scope26_headline": sha(ROOT / ".runtime/scope26/headline_result.json"),
        "param": sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param"),
        "bin": sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin"),
    }
    if actual != expected:
        raise SystemExit("SCOPE31_FROZEN_BASELINE_MISMATCH")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    final = {"status": "SERVO_SUPPLY_VOLTAGE_UNVERIFIED", "created_at_utc": datetime.now(timezone.utc).isoformat(), "baseline": actual, "pi_read_only_audit": "pi_read_only_audit.txt", "hardware": {"pan_servo": "MG90S", "tilt_servo": "MG90S", "pan_gpio": "BCM GPIO13", "tilt_gpio": "BCM GPIO12", "external_supply_user_confirmed": True, "supply_voltage_v": None, "common_ground_user_confirmed": True}, "gate": {"voltage_verified": False, "pwm_initialized": False, "gpio_initialized": False, "servo_object_created": False, "physical_movement_attempted": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0, "servo_writes": 0, "motor_writes": 0, "v3_test_accessed": False, "ai_to_servo_connected": False}, "read_only_discovery": {"pinctrl": True, "gpioinfo": True, "sysfs_pwmchip0": True, "active_servo_process_or_service": False, "pin_state": {"GPIO12": "none/input", "GPIO13": "none/input"}}, "required_user_evidence": ["measured voltage at external servo V+ to servo GND", "supply model or trusted setpoint", "whether measurement was under load", "confirmation servo V+ is not Pi 5V", "confirmation common ground"], "next_status_if_missing": "SERVO_SUPPLY_VOLTAGE_UNVERIFIED"}
    (RUNTIME / "final_status.json").write_text(json.dumps(final, indent=2) + "\n")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for source in (RUNTIME / "pi_read_only_audit.txt", RUNTIME / "final_status.json"):
        if source.exists(): shutil.copy2(source, ARTIFACTS / source.name)
    manifest = {"status": final["status"], "files": {p.name: sha(p) for p in sorted(ARTIFACTS.iterdir()) if p.is_file()}, "physical_output": False, "v3_test_accessed": False}
    (ARTIFACTS / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": final["status"], "baseline": actual, "physical_movement_attempted": False, "artifact_manifest_sha256": sha(ARTIFACTS / "ARTIFACT_MANIFEST.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
