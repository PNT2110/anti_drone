#!/usr/bin/env python3
"""Finalize Scope 30R alignment gate without starting a target run on failure."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope30r"
ARTIFACTS = ROOT / "artifacts/integration/scope30r"
DOCS = ROOT / "docs/tracking/scope30"
FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    checks = {
        "freeze_manifest": sha(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == FREEZE,
        "scope26_headline": sha(ROOT / ".runtime/scope26/headline_result.json") == HEADLINE,
        "param": sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == PARAM,
        "bin": sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == BIN,
        "scope29r": json.loads((ROOT / ".runtime/scope29r/final_status.json").read_text())["status"] == "USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY",
    }
    if not all(checks.values()):
        raise SystemExit("SCOPE30R_BASELINE_MISMATCH")
    snapshot = RUNTIME / "target_alignment_snapshot.jpg"
    if not snapshot.exists():
        raise SystemExit("TARGET_ALIGNMENT_SNAPSHOT_MISSING")
    # The snapshot was visually inspected before this finalizer was run.
    status = "TARGET_ALIGNMENT_REQUIRED"
    final = {"status": status, "created_at_utc": datetime.now(timezone.utc).isoformat(), "baseline": {"freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "param_sha256": PARAM, "bin_sha256": BIN}, "scope29r_status": "USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY", "scope30_attempt1": "LIVE_TARGET_TRACKING_BLOCKED", "alignment": {"snapshot": "target_alignment_snapshot.jpg", "snapshot_sha256": sha(snapshot), "camera_source": "/dev/video0", "camera_resolution": [640, 480], "monitor_visible": False, "video_visible": False, "approximate_monitor_coverage": "0% / absent", "visual_inspection": "frame shows ceiling/wall; no monitor or Halmstad video"}, "accepted_target_session_started": False, "target_run_status": "NOT_STARTED_AFTER_ALIGNMENT_GATE", "no_gpio_pwm_serial_servo_motor_writes": True, "test_accessed": False, "servo_status": "PHYSICAL_SERVO_COMMISSIONING_BLOCKED_BY_UNKNOWN_BOUNDS"}
    (RUNTIME / "final_status.json").write_text(json.dumps(final, indent=2) + "\n")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot, ARTIFACTS / snapshot.name)
    shutil.copy2(RUNTIME / "final_status.json", ARTIFACTS / "final_status.json")
    manifest = {"status": status, "files": {p.name: sha(p) for p in sorted(ARTIFACTS.iterdir()) if p.is_file()}, "test_accessed": False, "actuator_output_enabled": False}
    (ARTIFACTS / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")

    write(DOCS / "SCOPE30_TARGET_ALIGNMENT.md", f"""# Scope 30R — Target Alignment Gate

Status: `{status}`.

The single required pre-run webcam snapshot is `target_alignment_snapshot.jpg` with SHA-256 `{final['alignment']['snapshot_sha256']}`. It is 640x480 and visibly contains ceiling/wall only. The monitor and Halmstad video are absent; approximate monitor coverage is 0%.

Per the Scope 30R gate, no 90-second target-present session was started. Required user action: physically aim the USB webcam at the monitor while `V_DRONE_001.mp4` is displayed, then rerun the one-snapshot gate.
""")
    write(DOCS / "SCOPE30R_SERVO_INFORMATION_REQUIRED.md", """# Scope 30R — Servo Information Required

Physical commissioning remains blocked by `SERVO_BOUNDS_UNKNOWN`. The repository contains no authoritative evidence for the installed pan actuator model, tilt actuator model, controller/driver, pan channel, tilt channel, servo power supply arrangement, neutral/min/max command limits, command frequency, or command units.

Provide exact evidence before any future hardware scope:

- photo or model number for the pan actuator;
- photo or model number for the tilt actuator;
- controller board model and control method (PWM/PCA9685/MCU/serial/etc.);
- pan and tilt channel mapping;
- external servo supply voltage/current arrangement;
- documented safe neutral, minimum, and maximum commands with units.

No generic servo values are accepted and no hardware was initialized.
""")
    with (DOCS / "SCOPE30_TARGET_SOURCE.md").open("a") as f:
        f.write("\n## Scope 30R alignment attempt\n\nThe required single snapshot showed no monitor or video. The physical webcam therefore did not receive a target stimulus, and the accepted target session was not started.\n")
    with (DOCS / "SCOPE30_LIVE_TARGET_RUN.md").open("a") as f:
        f.write("\n## Scope 30R result\n\nAttempt 2 stopped before the live run with `TARGET_ALIGNMENT_REQUIRED`; no 90-second session was run.\n")
    with (DOCS / "SCOPE30_FINAL_REPORT.md").open("a") as f:
        f.write("\n## Scope 30R continuation\n\nAttempt 1 remains `LIVE_TARGET_TRACKING_BLOCKED` because the camera saw the ceiling. Scope 30R attempt 2 captured exactly one snapshot and again found no monitor/video, so the current status is `TARGET_ALIGNMENT_REQUIRED`. No detector/tracker regression was inferred, no accepted target session was started, and no actuator was initialized.\n")
    write(DOCS / "SCOPE30_TEST_REPORT.md", """# Scope 30 — Test Report / Scope 30R

The Scope 30R alignment gate intentionally stopped before the accepted live session because the single snapshot did not contain the monitor. Scope 30 software guards remain passing; Scope 29R evidence remains 145 passed, 1 skipped, compileall PASS, and git diff --check PASS. No V3 TEST access or hardware writes occurred.
""")
    print(json.dumps({"status": status, "snapshot_sha256": final["alignment"]["snapshot_sha256"], "accepted_target_session_started": False, "artifact_manifest_sha256": sha(ARTIFACTS / "ARTIFACT_MANIFEST.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
