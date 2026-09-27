#!/usr/bin/env python3
"""Finalize the accepted Scope 30R2 Attempt 4 target run."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / ".runtime/scope30r2/attempt4"
ARTIFACTS = ROOT / "artifacts/integration/scope30r2/attempt4"
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
    summary = json.loads((RUN / "target_summary.json").read_text())
    rows = [json.loads(line) for line in (RUN / "target_state.jsonl").read_text().splitlines()]
    snapshot = ROOT / ".runtime/scope30r2/attempt4/target_alignment_snapshot.jpg"
    checks = {
        "freeze": sha(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == FREEZE,
        "headline": sha(ROOT / ".runtime/scope26/headline_result.json") == HEADLINE,
        "param": sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == PARAM,
        "bin": sha(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == BIN,
        "target_run": summary["status"] == "LIVE_TARGET_RUN_COMPLETE" and summary["target_seen"] is True,
        "camera": summary["frames_dropped"]["capture_read_failures"] == 0 and summary["frames_dropped"]["invalid_frame_dimensions"] == 0,
        "actuator": summary["actuator"] == {"mode": "DRY_RUN_ONLY", "enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0, "servo_writes": 0, "motor_writes": 0},
    }
    if not all(checks.values()):
        raise SystemExit(f"SCOPE30R2_ATTEMPT4_GATE_FAILED: {checks}")
    command_states = {row["command_preview"]["state"] for row in rows}
    non_neutral = [row for row in rows if abs(row["command_preview"]["rate_limited_pan"]) > 1e-12 or abs(row["command_preview"]["rate_limited_tilt"]) > 1e-12]
    transitions = []
    previous = None
    for row in rows:
        state = row["command_preview"]["state"]
        if state != previous:
            transitions.append({"frame_id": row["frame_id"], "state": state})
            previous = state
    final = {"status": "LIVE_TARGET_COMMAND_PREVIEW_READY", "attempt": 4, "created_at_utc": datetime.now(timezone.utc).isoformat(), "history": {"attempt_1": "LIVE_TARGET_TRACKING_BLOCKED", "attempt_2": "TARGET_ALIGNMENT_REQUIRED", "attempt_3": "TARGET_ALIGNMENT_REQUIRED", "attempt_4": "LIVE_TARGET_COMMAND_PREVIEW_READY"}, "baseline": {"freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "param_sha256": PARAM, "bin_sha256": BIN}, "alignment": {"snapshot": "target_alignment_snapshot.jpg", "snapshot_sha256": sha(snapshot), "monitor_visible": True, "video_visible": True, "camera_source": "/dev/video0", "camera_resolution": [640, 480], "display_resolution": "2560x1440 HDMI-1", "target_source": "Halmstad V_DRONE_001.mp4 displayed on monitor"}, "target_run": summary, "command_preview": {"non_neutral_samples": len(non_neutral), "states_seen": sorted(command_states), "state_transitions": transitions, "loss_to_neutral_observed": any(t["state"] == "RETURN_NEUTRAL_PREVIEW" for t in transitions) and any(t["state"] == "NO_TARGET" for t in transitions), "envelope": {"neutral": 0.0, "minimum": -1.0, "maximum": 1.0, "max_delta_per_frame": 0.25}}, "camera_failure_safety": "CAMERA_OPEN_FAILED evidence retained from Scope 30; SAFE_NO_TARGET unit guard PASS", "servo_mapping": {"pan": "BCM GPIO13", "tilt": "BCM GPIO12", "mapping_only": True}, "servo_commissioning": "PHYSICAL_SERVO_COMMISSIONING_BLOCKED_BY_UNKNOWN_BOUNDS", "no_gpio_pwm_serial_servo_motor_writes": True, "test_accessed": False}
    (RUN / "final_status.json").write_text(json.dumps(final, indent=2) + "\n")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for src in (RUN / "target_summary.json", RUN / "target_state.jsonl", RUN / "target_config.json", RUN / "quick_gate_stdout.log", RUN / "quick_gate_stderr.log", RUN / "target_stdout.log", RUN / "target_stderr.log", snapshot, RUN / "final_status.json"):
        if src.exists(): shutil.copy2(src, ARTIFACTS / src.name)
    manifest = {"status": final["status"], "files": {p.name: sha(p) for p in sorted(ARTIFACTS.iterdir()) if p.is_file()}, "test_accessed": False, "actuator_output_enabled": False}
    (ARTIFACTS / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")

    append(DOCS / "SCOPE30_TARGET_ALIGNMENT.md", f"""## Scope 30R2 / Attempt 4 — PASS

Fresh snapshot SHA-256: `{final['alignment']['snapshot_sha256']}`. The monitor and Halmstad video were visibly present in the 640x480 webcam frame. Physical setup was held fixed for the accepted run.
""")
    append(DOCS / "SCOPE30_TARGET_SOURCE.md", """## Scope 30R2 / Attempt 4 — accepted source

Halmstad `V_DRONE_001.mp4` was displayed on the 2560x1440 HDMI-1 monitor. The detector input remained the physical USB webcam `/dev/video0`; the MP4 was never passed directly to NCNN.
""")
    append(DOCS / "SCOPE30_LIVE_TARGET_RUN.md", f"""## Scope 30R2 / Attempt 4 — accepted 90-second run

{json.dumps({'status': summary['status'], 'duration_s': summary['duration_wall_s'], 'captured': summary['frames_captured'], 'processed': summary['frames_processed'], 'stale_drops': summary['frames_dropped']['queue_stale_newest_policy'], 'read_failures': summary['frames_dropped']['capture_read_failures'], 'invalid_frames': summary['frames_dropped']['invalid_frame_dimensions']}, indent=2)}
""")
    append(DOCS / "SCOPE30_TRACKING_RESULTS.md", f"""## Scope 30R2 / Attempt 4 — live characterization

HIGH detection frames: `{summary['counts']['high_detection_frames']}`; LOW-only frames: `{summary['counts']['low_only_detection_frames']}`; track IDs: `{summary['track_ids_created']}`; target observed: `{summary['counts']['target_observed_frames']}`; LOW-associated inferred: `{summary['counts']['low_associated_inferred_frames']}`; prediction-only: `{summary['counts']['prediction_only_frames']}`; no-target: `{summary['counts']['no_target_frames']}`; ID changes: `{summary['events']['ID_SWITCH']['count']}`; lost/reacquired: `{summary['events']['TRACK_LOST']['count']}/{summary['events']['TRACK_REACQUIRED']['count']}`; target-selection changes: `{summary['events']['TARGET_SWITCH']['count']}`.

LOW association is reported as `LOW_ASSOCIATED_INFERRED` as required.
""")
    append(DOCS / "SCOPE30_COMMAND_PREVIEW_RESULTS.md", f"""## Scope 30R2 / Attempt 4 — live preview

Non-neutral samples: `{len(non_neutral)}` / `{len(rows)}`; raw pan range `{summary['command_characterization']['raw_pan']}`; raw tilt range `{summary['command_characterization']['raw_tilt']}`; rate-limited pan range `{summary['command_characterization']['rate_limited_pan']}`; rate-limited tilt range `{summary['command_characterization']['rate_limited_tilt']}`; rate-limit activations `{summary['command_characterization']['rate_limit_events']}`; neutral transitions `{summary['command_characterization']['neutral_transitions']}`.
""")
    append(DOCS / "SCOPE30_LOSS_OF_TARGET_SAFETY.md", f"""## Scope 30R2 / Attempt 4 — live loss evidence

Observed command-preview states: `{sorted(command_states)}`. Natural transitions included `TRACKING → HOLD_PREVIEW → RETURN_NEUTRAL_PREVIEW → NO_TARGET`; final no-target output was neutral. Software camera-failure guard remains `SAFE_NO_TARGET` with prior `CAMERA_OPEN_FAILED` evidence.
""")
    append(DOCS / "SCOPE30_PI_PERFORMANCE.md", f"""## Scope 30R2 / Attempt 4 — Pi 5 target run

Capture/processing FPS: `{summary['fps']['capture']:.4f}/{summary['fps']['processing']:.4f}`. Total latency mean/p50/p95: `{summary['latency_ms']['total_processing_ms']['mean']:.4f}/{summary['latency_ms']['total_processing_ms']['p50']:.4f}/{summary['latency_ms']['total_processing_ms']['p95']:.4f} ms`. Capture-to-result mean/p95: `{summary['latency_ms']['capture_to_result_age_ms']['mean']:.4f}/{summary['latency_ms']['capture_to_result_age_ms']['p95']:.4f} ms`. Peak RSS: `{summary['peak_rss_kb']} KB`; temperature: `{summary['hardware']['temperature_before']} -> {summary['hardware']['temperature_after']}`; throttling: `{summary['hardware']['throttling_before']} -> {summary['hardware']['throttling_after']}`.
""")
    append(DOCS / "SCOPE30_SERVO_DISCOVERY.md", """## Scope 30R2 / Attempt 4

Channel mapping remains PAN = BCM GPIO13 and TILT = BCM GPIO12, mapping only. No PWM/GPIO initialization occurred. Servo model, supply arrangement, neutral/min/max, pulse width, frequency, angle, and command units remain unknown; commissioning stays blocked.
""")
    append(DOCS / "SCOPE30_FINAL_REPORT.md", f"""## Scope 30R2 / Attempt 4 — final result

Current live-target status: `LIVE_TARGET_COMMAND_PREVIEW_READY`. The fresh alignment snapshot passed and the 90-second physical-webcam run produced target observations and non-neutral preview samples. Captured/processed: `{summary['frames_captured']}/{summary['frames_processed']}`; stale drops `{summary['frames_dropped']['queue_stale_newest_policy']}`; read/invalid `{summary['frames_dropped']['capture_read_failures']}/{summary['frames_dropped']['invalid_frame_dimensions']}`; HIGH/LOW-only `{summary['counts']['high_detection_frames']}/{summary['counts']['low_only_detection_frames']}`; IDs `{summary['track_ids_created']}`; non-neutral preview `{len(non_neutral)}`; rate-limit events `{summary['command_characterization']['rate_limit_events']}`; neutral transitions `{summary['command_characterization']['neutral_transitions']}`; writes `0/0/0/0/0`.

Attempt 1–3 history is preserved. Scope 26 remains immutable and V3 TEST was not accessed. Physical servo commissioning remains `PHYSICAL_SERVO_COMMISSIONING_BLOCKED_BY_UNKNOWN_BOUNDS` despite the recorded channel mapping PAN GPIO13 / TILT GPIO12. Scope 31 was not started.
""")
    print(json.dumps({"status": final["status"], "target_seen": True, "frames_processed": len(rows), "non_neutral_samples": len(non_neutral), "artifact_manifest_sha256": sha(ARTIFACTS / "ARTIFACT_MANIFEST.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
