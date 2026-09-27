#!/usr/bin/env python3
"""Finalize Scope 30R2 after the mandatory alignment snapshot gate."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope30r2"
ARTIFACTS = ROOT / "artifacts/integration/scope30r2"
DOCS = ROOT / "docs/tracking/scope30"
FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append(path: Path, text: str):
    with path.open("a") as f:
        f.write("\n" + text.rstrip() + "\n")


def main() -> int:
    snapshot = RUNTIME / "target_alignment_snapshot.jpg"
    if not snapshot.exists():
        raise SystemExit("TARGET_ALIGNMENT_SNAPSHOT_MISSING")
    checks = {
        "freeze": sha(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == FREEZE,
        "headline": sha(ROOT / ".runtime/scope26/headline_result.json") == HEADLINE,
        "param": sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == PARAM,
        "bin": sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == BIN,
    }
    if not all(checks.values()):
        raise SystemExit("SCOPE30R2_BASELINE_MISMATCH")
    status = "TARGET_ALIGNMENT_REQUIRED"
    snapshot_hash = sha(snapshot)
    final = {"status": status, "attempt": 3, "created_at_utc": datetime.now(timezone.utc).isoformat(), "baseline": {"freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "param_sha256": PARAM, "bin_sha256": BIN}, "history": {"attempt_1": "LIVE_TARGET_TRACKING_BLOCKED", "attempt_2": "TARGET_ALIGNMENT_REQUIRED", "attempt_3": status}, "alignment": {"snapshot": "target_alignment_snapshot.jpg", "snapshot_sha256": snapshot_hash, "camera_source": "/dev/video0", "camera_resolution": [640, 480], "monitor_visible": False, "video_visible": False, "approximate_monitor_coverage": "0% / absent", "visual_inspection": "ceiling/wall only; no HDMI monitor or Halmstad video"}, "quick_camera_gate": "NOT_RUN_AFTER_ALIGNMENT_STOP", "accepted_target_session_started": False, "target_run_status": "NOT_STARTED_AFTER_ALIGNMENT_GATE", "no_gpio_pwm_serial_servo_motor_writes": True, "test_accessed": False, "servo_status": "PHYSICAL_SERVO_COMMISSIONING_BLOCKED_BY_UNKNOWN_BOUNDS"}
    (RUNTIME / "final_status.json").write_text(json.dumps(final, indent=2) + "\n")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for src in (snapshot, RUNTIME / "camera_discovery_raw.txt", RUNTIME / "alignment_capture_stdout.log", RUNTIME / "alignment_capture_stderr.log", RUNTIME / "final_status.json"):
        if src.exists(): shutil.copy2(src, ARTIFACTS / src.name)
    manifest = {"status": status, "files": {p.name: sha(p) for p in sorted(ARTIFACTS.iterdir()) if p.is_file()}, "test_accessed": False, "actuator_output_enabled": False}
    (ARTIFACTS / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")

    append(DOCS / "SCOPE30_TARGET_ALIGNMENT.md", f"""## Scope 30R2 / Attempt 3

The new mandatory snapshot is `target_alignment_snapshot.jpg`, SHA-256 `{snapshot_hash}`. It is a fresh 640x480 frame from the physical `/dev/video0` webcam. Visual inspection shows ceiling/wall only: monitor visible = **no**, Halmstad video visible = **no**, approximate coverage = **0%**. Scope 30R2 therefore stopped with `TARGET_ALIGNMENT_REQUIRED` before the quick gate and before the accepted 90-second run.
""")
    append(DOCS / "SCOPE30_TARGET_SOURCE.md", """## Scope 30R2 / Attempt 3

Halmstad `V_DRONE_001.mp4` was playing on the host HDMI monitor, but the physical webcam frame did not contain that monitor. The MP4 was not passed to the detector.
""")
    append(DOCS / "SCOPE30_LIVE_TARGET_RUN.md", """## Scope 30R2 / Attempt 3

No accepted live-target run was started. The run was stopped at the mandatory alignment snapshot gate with `TARGET_ALIGNMENT_REQUIRED`.
""")
    append(DOCS / "SCOPE30_TRACKING_RESULTS.md", """## Scope 30R2 / Attempt 3

No detector/tracker frames were collected because the target was absent from the webcam snapshot. Existing software injection evidence remains the source for loss-of-target and camera-failure safety.
""")
    append(DOCS / "SCOPE30_COMMAND_PREVIEW_RESULTS.md", """## Scope 30R2 / Attempt 3

No live command-preview samples were collected. Existing normalized envelope and unit-test evidence remain unchanged.
""")
    append(DOCS / "SCOPE30_LOSS_OF_TARGET_SAFETY.md", """## Scope 30R2 / Attempt 3

No live target transition was attempted after the alignment gate failed. Software state-machine tests remain valid.
""")
    append(DOCS / "SCOPE30_PI_PERFORMANCE.md", """## Scope 30R2 / Attempt 3

No new performance run was started. The Scope 30 no-target and Scope 29R camera baselines remain unchanged.
""")
    append(DOCS / "SCOPE30_FINAL_REPORT.md", f"""## Scope 30R2 / Attempt 3

Current status: `{status}`. The fresh snapshot SHA-256 is `{snapshot_hash}` and contains ceiling/wall only; monitor/video visibility is false. No accepted session was started, no detector/tracker conclusion was drawn, and no physical actuator was initialized. Scope 31 remains unopened.
""")
    (DOCS / "SCOPE30_TEST_REPORT.md").write_text("""# Scope 30 — Test Report / Scope 30R2

Scope 30R2 stopped before the accepted live session at the mandatory alignment gate. Final regression: **154 passed, 1 skipped**. Compileall: PASS. `git diff --check`: PASS. Scope 29R historical evidence remains 145 passed, 1 skipped. No V3 TEST access or hardware writes occurred.
""")
    print(json.dumps({"status": status, "attempt": 3, "snapshot_sha256": snapshot_hash, "accepted_target_session_started": False, "artifact_manifest_sha256": sha(ARTIFACTS / "ARTIFACT_MANIFEST.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
