#!/usr/bin/env python3
"""Finalize Scope 30 without turning a no-target run into a false PASS."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope30"
ARTIFACTS = ROOT / "artifacts/integration/scope30"
DOCS = ROOT / "docs/tracking/scope30"
FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str):
    return json.loads((RUNTIME / name).read_text())


def md_table(rows):
    return "\n".join(["| Metric | Value |", "|---|---|"] + [f"| {key} | {value} |" for key, value in rows])


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def main() -> int:
    checks = {
        "freeze_manifest": digest(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == FREEZE,
        "scope26_headline": digest(ROOT / ".runtime/scope26/headline_result.json") == HEADLINE,
        "param": digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == PARAM,
        "bin": digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == BIN,
        "scope29r": load("../scope29r/final_status.json") if False else True,
    }
    if not all(checks[key] for key in ("freeze_manifest", "scope26_headline", "param", "bin")):
        raise SystemExit("SCOPE30_BASELINE_MISMATCH")
    scope29r = json.loads((ROOT / ".runtime/scope29r/final_status.json").read_text())
    if scope29r["status"] != "USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY":
        raise SystemExit("SCOPE29R_CLOSEOUT_NOT_VERIFIED")
    target = load("target_summary.json")
    invalid = load("invalid_camera_summary.json")
    target_rows = [json.loads(line) for line in (RUNTIME / "target_state.jsonl").read_text().splitlines()]
    bad_resolution = [row for row in target_rows if row["source_resolution"] != [640, 480]]
    status = "LIVE_TARGET_COMMAND_PREVIEW_READY" if target["target_seen"] and not bad_resolution and target["frames_dropped"]["capture_read_failures"] == 0 and target["frames_dropped"]["invalid_frame_dimensions"] == 0 else "LIVE_TARGET_TRACKING_BLOCKED"
    final = {"status": status, "created_at_utc": datetime.now(timezone.utc).isoformat(), "freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "param_sha256": PARAM, "bin_sha256": BIN, "scope29r_status": scope29r["status"], "scope29r_regression_reference": {"pytest_passed": 145, "pytest_skipped": 1, "compileall": "PASS", "git_diff_check": "PASS"}, "target": target, "invalid_camera": invalid, "rows_checked": len(target_rows), "bad_resolutions": len(bad_resolution), "servo_bounds": "SERVO_BOUNDS_UNKNOWN", "physical_commissioning": "PHYSICAL_SERVO_COMMISSIONING_BLOCKED_BY_UNKNOWN_BOUNDS", "no_gpio_pwm_serial_servo_motor_writes": True, "no_test_access": True, "no_autostart": True}
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / "final_status.json").write_text(json.dumps(final, indent=2) + "\n")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for name in ("target_summary.json", "target_state.jsonl", "invalid_camera_summary.json", "target_config.json", "invalid_camera_config.json", "camera_discovery_raw.txt", "v4l2_probe_stdout.log", "v4l2_probe_stderr.log", "invalid_camera_stdout.log", "invalid_camera_stderr.log", "target_stdout.log", "target_stderr.log", "final_status.json"):
        if (RUNTIME / name).exists():
            shutil.copy2(RUNTIME / name, ARTIFACTS / name)
    artifact_manifest = {"status": status, "files": {p.name: digest(p) for p in sorted(ARTIFACTS.iterdir()) if p.is_file()}, "freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "test_accessed": False, "actuator_output_enabled": False}
    (ARTIFACTS / "ARTIFACT_MANIFEST.json").write_text(json.dumps(artifact_manifest, indent=2) + "\n")

    target_source = "Halmstad V_DRONE_001.mp4 displayed on host HDMI-1 2560x1440; pipeline input remained physical USB webcam /dev/video0. A webcam snapshot during the run showed ceiling, so the target was not actually visible through the camera."
    write(DOCS / "SCOPE30_INPUT_AUDIT.md", f"""# Scope 30 — Input Audit

{md_table([('Scope 29R', scope29r['status']), ('Freeze manifest', f'{FREEZE} PASS'), ('Scope 26 headline', f'{HEADLINE} PASS'), ('NCNN param/bin', 'PASS'), ('Detector', 'YOLOv8n-480 NCNN FP32'), ('HIGH / LOW', '>=0.25 / 0.10–<0.25'), ('NMS', 'IoU 0.70, once per inference'), ('Tracker', 'bytetrack_motion_adaptive'), ('V3 TEST', 'not accessed'), ('Actuation', 'disabled')])}

The frozen artifacts and Scope 29R recovered-camera evidence were verified before the target-presence attempt.
""")
    write(DOCS / "SCOPE30_SCOPE29R_CLOSEOUT.md", f"""# Scope 30 — Scope 29R Closeout

The original Scope 29 `CAMERA_RUNTIME_BLOCKED` history is retained. Scope 29R is verified as `{scope29r['status']}`. The exact prior Scope 29R regression evidence was **145 passed, 1 skipped**, with compileall PASS and `git diff --check` PASS. Scope 30 did not alter the frozen detector or Scope 26 headline.
""")
    write(DOCS / "SCOPE30_SERVO_DISCOVERY.md", """# Scope 30 — Servo Discovery

Repository inspection found no authoritative servo model, pan/tilt channel map, GPIO/PWM controller, serial controller, power arrangement, or calibrated command-unit specification. The repository’s dry-run layers expose preview fields only and do not initialize hardware.

Status: `SERVO_BOUNDS_UNKNOWN`.

Physical commissioning is therefore `PHYSICAL_SERVO_COMMISSIONING_BLOCKED_BY_UNKNOWN_BOUNDS`. No GPIO mode, PWM, serial, servo, motor, or power rail was touched.
""")
    write(DOCS / "SCOPE30_TARGET_SOURCE.md", f"""# Scope 30 — Target Source

{target_source}

The Halmstad video was used only as a visual screen-presented diagnostic source; it was not passed to the detector. The accepted target-present gate was not achieved because the physical webcam view did not contain the monitor target.
""")
    write(DOCS / "SCOPE30_LIVE_TARGET_RUN.md", f"""# Scope 30 — Live Target Run

Status: `{status}`.

{md_table([('Declared duration', f"{target['duration_wall_s']:.3f} s / {target['duration_requested_s']:.1f} s"), ('Captured / processed', f"{target['frames_captured']} / {target['frames_processed']}"), ('Stale queue drops', target['frames_dropped']['queue_stale_keep_newest'] if 'queue_stale_keep_newest' in target['frames_dropped'] else target['frames_dropped']['queue_stale_newest_policy']), ('Read failures / invalid frames', f"{target['frames_dropped']['capture_read_failures']} / {target['frames_dropped']['invalid_frame_dimensions']}" if 'invalid_frame_dimensions' in target['frames_dropped'] else f"{target['frames_dropped']['capture_read_failures']} / {target['frames_dropped']['invalid_frame_dimensions'] if 'invalid_frame_dimensions' in target['frames_dropped'] else target['frames_dropped']['invalid_frame_dimensions']}"), ('HIGH detection frames', target['counts']['high_detection_frames']), ('LOW-only frames', target['counts']['low_only_detection_frames']), ('Target observed / inferred / predicted / none', f"{target['counts']['target_observed_frames']} / {target['counts']['low_associated_inferred_frames']} / {target['counts']['prediction_only_frames']} / {target['counts']['no_target_frames']}"), ('Track IDs', target['track_ids_created']), ('Target seen through webcam', target['target_seen'])])}

The session was run against the physical webcam only. No manual target alignment was available before the declared run; a snapshot showed the camera aimed at the ceiling.
""")
    write(DOCS / "SCOPE30_TRACKING_RESULTS.md", f"""# Scope 30 — Tracking Results

No HIGH or LOW detections occurred in the accepted 90-second camera session, so no track ID, target state, loss/reacquisition, or target-center trajectory could be characterized from a real camera-present target. The no-target path recorded {target['counts']['no_target_frames']} frames and did not fabricate a target.

Software event-injection tests separately cover `HIGH_OBSERVED → PREDICTED → NONE`, low-associated state naming, safe neutral transition, and camera-failure safe state.
""")
    write(DOCS / "SCOPE30_COMMAND_PREVIEW_CONTRACT.md", """# Scope 30 — Command Preview Contract

Frame center is `(width/2, height/2)`. Pixel error is `target_center - frame_center`. Normalized error is `2 * pixel_error / frame_dimension`, clamped to `[-1, +1]` only in the software preview layer. Raw normalized desired pan/tilt equals the normalized error for TRACKING and HOLD_PREVIEW states.

Envelope is normalized-only: neutral `0.0`, minimum `-1.0`, maximum `+1.0`, maximum change `0.25` per frame. The preview reports raw, bounded, and rate-limited values. No physical pulse width, angle, PWM duty, GPIO, serial value, or hardware direction was inferred.
""")
    write(DOCS / "SCOPE30_COMMAND_PREVIEW_RESULTS.md", """# Scope 30 — Command Preview Results

The software-only preview implementation and unit guards pass for centered, edge, observed, LOW-associated, predicted, no-target, and camera-failure inputs. Live command samples were neutral because the physical webcam saw no target. This is not servo performance evidence.
""")
    write(DOCS / "SCOPE30_LOSS_OF_TARGET_SAFETY.md", """# Scope 30 — Loss-of-Target Safety

The preview state machine is deterministic: observed target → `TRACKING`; predicted target → `HOLD_PREVIEW`; target absent → `RETURN_NEUTRAL_PREVIEW` and then `NO_TARGET`; camera failure → `SAFE_NO_TARGET`. After target invalidation, the preview cannot retain a non-neutral command indefinitely. Physical output remains disabled.
""")
    write(DOCS / "SCOPE30_PI_PERFORMANCE.md", f"""# Scope 30 — Pi Performance

{md_table([('Camera source', '/dev/video0, 640x480 MJPG requested 25 FPS'), ('Capture / processing FPS', f"{target['fps']['capture']:.4f} / {target['fps']['processing']:.4f}"), ('Total latency mean/p50/p95', f"{target['latency_ms']['total_processing_ms']['mean']:.4f} / {target['latency_ms']['total_processing_ms']['p50']:.4f} / {target['latency_ms']['total_processing_ms']['p95']:.4f} ms"), ('Capture-to-result mean/p95', f"{target['latency_ms']['capture_to_result_age_ms']['mean']:.4f} / {target['latency_ms']['capture_to_result_age_ms']['p95']:.4f} ms"), ('Temperature', f"{target['hardware'].get('temperature_before')} -> {target['hardware'].get('temperature_after')}"), ('Throttling', f"{target['hardware'].get('throttling_before')} -> {target['hardware'].get('throttling_after')}"), ('Peak RSS', target['peak_rss_kb'])])}

This performance result is operational live-camera evidence but not target-tracking accuracy or servo performance.
""")
    write(DOCS / "SCOPE30_DRYRUN_SAFETY.md", f"""# Scope 30 — Dry-Run Safety

{md_table([('Invalid camera test', invalid['status']), ('Actuator mode', invalid['actuator']['mode']), ('GPIO/PWM/serial writes', '0/0/0'), ('Servo/motor writes', '0/0'), ('V3 TEST access', False), ('Autostart/system service', 'none'), ('Hardware sink imports', 'blocked by source guard')])}
""")
    write(DOCS / "SCOPE30_TEST_REPORT.md", """# Scope 30 — Test Report

Scope 30 unit guards: PASS (5 passed, 1 skipped before live artifacts). The full final suite result is recorded after this report is generated. Compileall and `git diff --check` are required final gates. The runtime invalid-camera test passed with `CAMERA_OPEN_FAILED`, model not loaded, and dry-run actuator disabled.
""")
    write(DOCS / "SCOPE30_FINAL_REPORT.md", f"""# Scope 30 — Final Report

Final status: `{status}`.

{md_table([('Scope 29R final status', scope29r['status']), ('Target source', 'Halmstad video displayed on HDMI monitor; physical webcam remained detector input'), ('Target visible through physical webcam', target['target_seen']), ('Duration / captured / processed', f"{target['duration_wall_s']:.2f}s / {target['frames_captured']} / {target['frames_processed']}"), ('HIGH / LOW-only frames', f"{target['counts']['high_detection_frames']} / {target['counts']['low_only_detection_frames']}"), ('Track IDs / ID changes', f"{target['track_ids_created']} / {target['events']['ID_SWITCH']['count']}"), ('Lost / reacquired / predicted / none', f"{target['events']['TRACK_LOST']['count']} / {target['events']['TRACK_REACQUIRED']['count']} / {target['counts']['prediction_only_frames']} / {target['counts']['no_target_frames']}"), ('Error/command preview', 'No live target samples; software contract tests PASS'), ('Camera failure safety', invalid['status']), ('Servo discovery/bounds', 'No authoritative hardware config; SERVO_BOUNDS_UNKNOWN'), ('Writes', '0 GPIO / 0 PWM / 0 serial / 0 servo / 0 motor'), ('Performance', f"{target['fps']['processing']:.4f} FPS; {target['latency_ms']['total_processing_ms']['mean']:.4f} ms mean"), ('Temperature/throttling', f"{target['hardware'].get('temperature_before')} -> {target['hardware'].get('temperature_after')}; {target['hardware'].get('throttling_before')} -> {target['hardware'].get('throttling_after')}"), ('Scope 26 headline', HEADLINE), ('V3 TEST', 'not accessed')])}

The live target-presence acceptance gate is blocked because the webcam was aimed at the ceiling rather than the monitor target. This is `LIVE_TARGET_TRACKING_BLOCKED`, not a detector regression. Physical servo commissioning is independently blocked by unknown servo bounds. No Scope 31 was started.
""")
    print(json.dumps({"status": status, "target_seen": target["target_seen"], "artifact_manifest_sha256": digest(ARTIFACTS / "ARTIFACT_MANIFEST.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
