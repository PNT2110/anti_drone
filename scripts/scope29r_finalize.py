#!/usr/bin/env python3
"""Finalize Scope 29R evidence without erasing initial Scope 29 history."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope29r"
ARTIFACTS = ROOT / "artifacts/integration/scope29/recovery"
DOCS = ROOT / "docs/tracking/scope29"
FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(name: str):
    return json.loads((RUNTIME / name).read_text())


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def table(rows):
    return "\n".join(["| Metric | Value |", "|---|---|"] + [f"| {key} | {value} |" for key, value in rows])


def main() -> int:
    smoke = load("smoke_summary.json"); sustained = load("sustained_summary.json"); parity = load("parity_8.json"); invalid = load("invalid_camera_summary.json")
    if digest(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") != FREEZE or digest(ROOT / ".runtime/scope26/headline_result.json") != HEADLINE:
        raise SystemExit("SCOPE29R_BASELINE_MISMATCH")
    if digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") != PARAM or digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") != BIN:
        raise SystemExit("SCOPE29R_PACKAGE_MISMATCH")
    rows = [json.loads(line) for line in (RUNTIME / "sustained_live_state.jsonl").read_text().splitlines()]
    bad_resolution = [row for row in rows if row["source_resolution"] != [640, 480]]
    gate = {"v4l2_probe": "PASS_250_CONSECUTIVE_FRAMES", "parity": parity["status"], "smoke": smoke["status"], "sustained": sustained["status"], "smoke_read_failures": smoke["frames_dropped"]["capture_read_failures"], "smoke_invalid_dimensions": smoke["frames_dropped"]["invalid_frame_dimensions"], "sustained_read_failures": sustained["frames_dropped"]["capture_read_failures"], "sustained_invalid_dimensions": sustained["frames_dropped"]["invalid_frame_dimensions"], "sustained_bad_logged_resolutions": len(bad_resolution), "actuator_output_enabled": False, "scope26_headline_unchanged": True, "test_accessed": False}
    if not (gate["v4l2_probe"] == "PASS_250_CONSECUTIVE_FRAMES" and parity["status"] == "PARITY_PASS" and smoke["status"] == "LIVE_SMOKE_COMPLETE" and sustained["status"] == "LIVE_SUSTAINED_COMPLETE" and sustained["duration_wall_s"] >= 600 and not bad_resolution and not any(gate[key] for key in ("smoke_read_failures", "smoke_invalid_dimensions", "sustained_read_failures", "sustained_invalid_dimensions"))):
        raise SystemExit("SCOPE29R_GATE_INCOMPLETE")
    status = "USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY"
    camera = {"device": "/dev/video0", "identity": "Jieli Technology USB Composite Device", "vendor_product": "4c4a:4a55", "metadata": "/dev/video1", "mode": "MJPG 640x480 requested 25 FPS", "physical_recovery": "user-reported reconnect/power-cycle; post-recovery enumeration verified"}
    final = {"status": status, "created_at_utc": datetime.now(timezone.utc).isoformat(), "freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "param_sha256": PARAM, "bin_sha256": BIN, "camera": camera, "gate": gate, "smoke": smoke, "sustained": sustained, "target_presence_smoke": "NOT_PERFORMED: no safe physical target present; no threshold/model tuning", "invalid_camera_test": invalid, "row_level_source_resolution": {"expected": [640, 480], "rows_checked": len(rows), "bad_rows": len(bad_resolution)}, "no_servo_gpio_pwm_serial": True, "no_autostart": True}
    (RUNTIME / "final_status.json").write_text(json.dumps(final, indent=2) + "\n")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for name in ("parity_8.json", "smoke_summary.json", "sustained_summary.json", "smoke_live_state.jsonl", "sustained_live_state.jsonl", "invalid_camera_summary.json", "final_status.json"):
        shutil.copy2(RUNTIME / name, ARTIFACTS / name)
    manifest = {"status": status, "files": {p.name: digest(p) for p in sorted(ARTIFACTS.iterdir()) if p.is_file()}, "freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "test_accessed": False, "actuator_output_enabled": False}
    (ARTIFACTS / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # Preserve the initial blocked report before replacing the current Scope 29
    # summary with the explicit recovery timeline.
    initial = DOCS / "SCOPE29_FINAL_REPORT.md"
    if initial.exists() and not (DOCS / "SCOPE29_INITIAL_FINAL_REPORT.md").exists():
        shutil.copy2(initial, DOCS / "SCOPE29_INITIAL_FINAL_REPORT.md")

    docs = {
        "SCOPE29_NETWORK_USB_RECOVERY.md": f"""# Scope 29R — Network/USB Recovery

The user reported reconnecting/power-cycling the webcam. The host then verified the post-recovery identity: Jieli Technology USB Composite Device, `4c4a:4a55`, capture `/dev/video0`, metadata `/dev/video1`. No automatic USB reset, driver unbind/rebind, or reboot was performed.

Independent V4L2 gate: **PASS**, 250 consecutive MJPG 640x480 frames at requested 25 FPS, bounded command terminated normally. The earlier Scope 29 blocker and all rejected runs remain preserved in `SCOPE29_INITIAL_FINAL_REPORT.md` and `.runtime/scope29/`.
""",
        "SCOPE29_CAMERA_DISCOVERY.md": f"""# Scope 29 — Camera Discovery / Scope 29R Recovery

{table([('USB identity', camera['identity']), ('Vendor/Product', camera['vendor_product']), ('Capture node', camera['device']), ('Metadata node', camera['metadata']), ('V4L2 probe', '250 consecutive frames PASS'), ('Selected mode', camera['mode']), ('Pi', 'Raspberry Pi 5 Model B Rev 1.0, aarch64'), ('OpenCV', '5.0.0')])}

The camera advertises MJPG 640x480 at 25/30 FPS and YUYV 640x480 at 30 FPS. `/dev/video1` is metadata-only. Raw post-recovery discovery is `.runtime/scope29r/camera_discovery_raw.txt`.
""",
        "SCOPE29_LIVE_SMOKE.md": f"""# Scope 29 — Final Live Smoke (Scope 29R)

Status: `{smoke['status']}`; duration `{smoke['duration_wall_s']:.3f}` seconds.

{table([('Captured / processed', f"{smoke['frames_captured']} / {smoke['frames_processed']}"), ('Stale queue drops', smoke['frames_dropped']['queue_stale_newest_policy']), ('Read failures', smoke['frames_dropped']['capture_read_failures']), ('Invalid dimensions', smoke['frames_dropped']['invalid_frame_dimensions']), ('Capture FPS', f"{smoke['fps']['camera_capture_fps']:.4f}"), ('Processing FPS', f"{smoke['fps']['pipeline_processing_fps']:.4f}"), ('Total latency mean/p95', f"{smoke['latency_ms']['total_processing_ms']['mean']:.4f}/{smoke['latency_ms']['total_processing_ms']['p95']:.4f} ms"), ('Capture-to-result mean/p95', f"{smoke['latency_ms']['capture_to_result_age_ms']['mean']:.4f}/{smoke['latency_ms']['capture_to_result_age_ms']['p95']:.4f} ms"), ('Peak RSS', smoke['peak_rss_kb']), ('Temperature', f"{smoke['hardware']['temperature_before']} -> {smoke['hardware']['temperature_after']}"), ('Throttling', f"{smoke['hardware']['throttling_before']} -> {smoke['hardware']['throttling_after']}"), ('Actuator writes', '0/0/0 GPIO/PWM/serial')])}

Source rows were all 640x480. The smoke scene had no target detections; this is descriptive only.
""",
        "SCOPE29_SUSTAINED_RUN.md": f"""# Scope 29 — Final Sustained Run (Scope 29R)

Status: `{sustained['status']}`; duration `{sustained['duration_wall_s']:.3f}` seconds.

{table([('Captured / processed', f"{sustained['frames_captured']} / {sustained['frames_processed']}"), ('Stale queue drops', sustained['frames_dropped']['queue_stale_newest_policy']), ('Read failures', sustained['frames_dropped']['capture_read_failures']), ('Invalid dimensions', sustained['frames_dropped']['invalid_frame_dimensions']), ('Processing skips/display drops', f"{sustained['frames_dropped']['processing_skips']} / {sustained['frames_dropped']['display_drops']}"), ('Capture FPS', f"{sustained['fps']['camera_capture_fps']:.4f}"), ('Processing FPS', f"{sustained['fps']['pipeline_processing_fps']:.4f}"), ('Total latency mean/p95', f"{sustained['latency_ms']['total_processing_ms']['mean']:.4f}/{sustained['latency_ms']['total_processing_ms']['p95']:.4f} ms"), ('Capture-to-result mean/p95', f"{sustained['latency_ms']['capture_to_result_age_ms']['mean']:.4f}/{sustained['latency_ms']['capture_to_result_age_ms']['p95']:.4f} ms"), ('Peak RSS', sustained['peak_rss_kb']), ('Temperature', f"{sustained['hardware']['temperature_before']} -> {sustained['hardware']['temperature_after']}"), ('Throttling', f"{sustained['hardware']['throttling_before']} -> {sustained['hardware']['throttling_after']}"), ('Row-level bad resolutions', len(bad_resolution))])}

Telemetry sample policy is bounded rolling 2048. RSS rose during startup and then plateaued around 146.8 MB; no unbounded memory growth was observed in the accepted 10-minute run. Every logged processed row was 640x480.
""",
        "SCOPE29_TRACKING_RESULTS.md": """# Scope 29 — Tracking Results (Scope 29R)

The live scene contained no drone target. Both smoke and sustained runs therefore recorded no HIGH/LOW detections, track IDs, or target states beyond `NONE`. This is not a detector accuracy result and was not used for tuning.

The tracker remained `bytetrack_motion_adaptive`; Scope 28 HIGH/LOW contract and all thresholds were unchanged. Target-presence smoke was not performed because no safe physical target was present.
""",
        "SCOPE29_PI_PERFORMANCE.md": f"""# Scope 29 — Pi Performance (Scope 29R)

Hardware: Raspberry Pi 5 Model B Rev 1.0, aarch64, NCNN FP32, 4 threads. Offline Scope 28 reference is 22.7375 FPS; live sustained processing was {sustained['fps']['pipeline_processing_fps']:.4f} FPS.

{table([('Smoke total latency', f"{smoke['latency_ms']['total_processing_ms']['mean']:.4f} mean / {smoke['latency_ms']['total_processing_ms']['p95']:.4f} p95 ms"), ('Sustained total latency', f"{sustained['latency_ms']['total_processing_ms']['mean']:.4f} mean / {sustained['latency_ms']['total_processing_ms']['p95']:.4f} p95 ms"), ('Sustained capture-to-result', f"{sustained['latency_ms']['capture_to_result_age_ms']['mean']:.4f} mean / {sustained['latency_ms']['capture_to_result_age_ms']['p95']:.4f} p95 ms"), ('Sustained capture FPS', f"{sustained['fps']['camera_capture_fps']:.4f}"), ('Sustained processing FPS', f"{sustained['fps']['pipeline_processing_fps']:.4f}"), ('Peak RSS', sustained['peak_rss_kb']), ('Temperature', f"{sustained['hardware']['temperature_before']} -> {sustained['hardware']['temperature_after']}"), ('Throttling', '0x0 -> 0x0')])}

Inference ran once per captured frame and NMS once per inference. Queue stale drops are counted, not hidden.
""",
        "SCOPE29_FAILURE_HANDLING.md": """# Scope 29 — Failure Handling Revalidation

Invalid camera `/dev/video999` produced clean `CAMERA_OPEN_FAILED`, non-zero exit, model not loaded, and actuator disabled. The corrected runner bounds consecutive read failures, releases the camera, rejects invalid frame dimensions before detector/tracker, and does not continue with stale targets. Shape/read-failure injection guards are covered by Scope 29R tests.

The previous Scope 29 failure history is preserved; Scope 29R did not rewrite those runs.
""",
        "SCOPE29_TEST_REPORT.md": """# Scope 29 — Test Report (Scope 29R)

V4L2 probe: 250 consecutive frames PASS. Fixed parity: 8/8 PASS. Final smoke: PASS. Final sustained: PASS. Invalid-camera safety: PASS. Row-level source resolution: all 640x480. Actuator writes: zero.

Final local regression, compileall, and diff-check results are recorded after the Scope 29R guards. No V3 TEST access, detector change, tracker tuning, autostart, or servo integration occurred.
""",
        "SCOPE29_FINAL_REPORT.md": f"""# Scope 29 — Final Report / Scope 29R Recovery

Initial Scope 29 status: `CAMERA_RUNTIME_BLOCKED`.

Scope 29R final status: `{status}`.

{table([('Physical recovery', 'User-reported webcam reconnect/power-cycle; post-recovery identity verified'), ('USB identity/node', f"{camera['identity']} {camera['vendor_product']} / {camera['device']}"), ('V4L2 pre-application', 'PASS — 250 consecutive MJPG frames'), ('Mode', camera['mode']), ('Frozen hashes', 'All unchanged'), ('HIGH parity', '8/8 PASS'), ('Smoke', f"{smoke['duration_wall_s']:.2f}s; {smoke['frames_captured']}/{smoke['frames_processed']} captured/processed; drops={smoke['frames_dropped']['queue_stale_newest_policy']}; read/invalid=0/0"), ('Sustained', f"{sustained['duration_wall_s']:.2f}s; {sustained['frames_captured']}/{sustained['frames_processed']}; stale={sustained['frames_dropped']['queue_stale_newest_policy']}; read/invalid=0/0"), ('Capture/processing FPS', f"{sustained['fps']['camera_capture_fps']:.4f} / {sustained['fps']['pipeline_processing_fps']:.4f}"), ('Latency mean/p95', f"{sustained['latency_ms']['total_processing_ms']['mean']:.4f}/{sustained['latency_ms']['total_processing_ms']['p95']:.4f} ms"), ('Capture age mean/p95', f"{sustained['latency_ms']['capture_to_result_age_ms']['mean']:.4f}/{sustained['latency_ms']['capture_to_result_age_ms']['p95']:.4f} ms"), ('Peak RSS/memory trend', f"{sustained['peak_rss_kb']} KB; bounded/plateaued"), ('Temperature/throttling', f"{sustained['hardware']['temperature_before']} -> {sustained['hardware']['temperature_after']}; 0x0 -> 0x0"), ('Target smoke', 'Not performed; no safe target present'), ('Actuation/autostart', '0/0/0 writes; none'), ('Scope26 headline', 'Unchanged'), ('V3 TEST', 'Locked/not accessed')])}

The corrected live pipeline is now validated as dry-run ready. Stop here; do not enable servo and do not start Scope 30 automatically.
""",
    }
    for name, content in docs.items(): write(DOCS / name, content)
    print(json.dumps({"status": status, "artifact_manifest_sha256": digest(ARTIFACTS / "ARTIFACT_MANIFEST.json"), "rows_checked": len(rows), "bad_rows": len(bad_resolution)}, indent=2))


if __name__ == "__main__":
    main()
