#!/usr/bin/env python3
"""Create Scope 29 reports, preserving accepted and rejected live evidence."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope29"
ARTIFACTS = ROOT / "artifacts/integration/scope29"
DOCS = ROOT / "docs/tracking/scope29"
FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def sha256(path: Path) -> str:
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
    return "\n".join(["| Metric | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows])


def main() -> int:
    audit = load("input_audit.json")
    parity = load("parity_8.json")
    invalid = load("invalid_camera_summary.json")
    smoke_prior = load("smoke_ring_bug_summary.json")
    smoke_latest = load("smoke_summary.json")
    sustained_30 = load("sustained_30fps_summary.json")
    sustained_unbounded = load("sustained_25fps_unbounded_telemetry_summary.json")
    sustained_ring = load("sustained_25fps_ring_summary.json")
    sustained_copy = load("sustained_25fps_copy_summary.json")
    latest_final_summary = load("sustained_summary.json")
    if sha256(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") != FREEZE or sha256(ROOT / ".runtime/scope26/headline_result.json") != HEADLINE:
        raise SystemExit("SCOPE29_BASELINE_MISMATCH")
    if sha256(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") != PARAM or sha256(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") != BIN:
        raise SystemExit("SCOPE29_PACKAGE_MISMATCH")
    if parity["status"] != "PARITY_PASS" or invalid["status"] != "CAMERA_OPEN_FAILED":
        raise SystemExit("SCOPE29_GATE_EVIDENCE_MISMATCH")
    camera = {"device": "/dev/video0", "identity": "Jieli Technology USB Composite Device (USB Camer)", "vendor_id": "4c4a", "product_id": "4a55", "capture_node": "/dev/video0", "metadata_node": "/dev/video1", "selected_mode": {"pixel_format": "MJPG", "width": 640, "height": 480, "requested_fps": 25}, "supported": {"MJPG": ["1920x1080@25/30", "1280x720@25/30", "640x480@25/30", "640x360@25/30", "352x288@25/30"], "YUYV": ["640x480@30", "640x360@30", "352x288@30", "320x240@30"]}}
    run_status = "CAMERA_RUNTIME_BLOCKED"
    machine = {"status": run_status, "created_at_utc": datetime.now(timezone.utc).isoformat(), "freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "candidate_id": audit["candidate_id"], "detector_hashes": {"param": PARAM, "bin": BIN}, "scope28_high_equivalence": audit["scope28_high_equivalence"], "scope29_parity_8": parity, "camera": camera, "accepted_smoke_prior": smoke_prior, "latest_smoke": smoke_latest, "sustained_attempts": {"fps30_read_failure": sustained_30, "fps25_unbounded_telemetry": {k: sustained_unbounded.get(k) for k in ("status", "duration_wall_s", "frames_captured", "frames_processed", "frames_dropped", "fps", "errors")}, "fps25_ring_invalid_source": {k: sustained_ring.get(k) for k in ("status", "duration_wall_s", "frames_captured", "frames_processed", "frames_dropped", "fps", "camera", "errors")}, "fps25_copy_invalid_source": {k: sustained_copy.get(k) for k in ("status", "duration_wall_s", "frames_captured", "frames_processed", "frames_dropped", "fps", "camera", "errors")}, "latest_final_guard_run": {k: latest_final_summary.get(k) for k in ("status", "duration_wall_s", "frames_captured", "frames_processed", "frames_dropped", "fps", "errors")}}, "invalid_camera_test": invalid, "v4l2_stream_probe": "did not complete 100 MJPG frames within 20 seconds; no process held /dev/video0", "user_action_required": "Reconnect or power-cycle the USB webcam, confirm /dev/video0 stream works, then rerun Scope 29 command.", "actuator_output_enabled": False, "webcam_processing_local_only": True, "v3_test_accessed": False}
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / "camera_discovery.json").write_text(json.dumps(camera, indent=2) + "\n")
    (RUNTIME / "scope29_final_status.json").write_text(json.dumps(machine, indent=2) + "\n")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for name in ("input_audit.json", "camera_discovery.json", "parity_8.json", "invalid_camera_summary.json", "smoke_ring_bug_summary.json", "smoke_summary.json", "sustained_30fps_summary.json", "sustained_25fps_unbounded_telemetry_summary.json", "sustained_25fps_ring_summary.json", "sustained_25fps_copy_summary.json", "scope29_final_status.json"):
        shutil.copy2(RUNTIME / name, ARTIFACTS / name)
    manifest = {"status": run_status, "files": {p.name: sha256(p) for p in sorted(ARTIFACTS.iterdir()) if p.is_file()}, "freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "actuator_output_enabled": False, "autostart_created": False, "test_accessed": False}
    (ARTIFACTS / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    max_conf = max(row["comparison"]["max_confidence_abs"] for row in parity["images"])
    min_iou = min(row["comparison"]["min_bbox_iou"] for row in parity["images"])
    docs = {
        "SCOPE29_INPUT_AUDIT.md": f"""# Scope 29 — Input Audit

Status: `INPUTS_VERIFIED`; final live status: `{run_status}`.

{table([('Scope 25 freeze SHA-256', FREEZE), ('Scope 26 headline SHA-256', HEADLINE), ('NCNN param SHA-256', PARAM), ('NCNN bin SHA-256', BIN), ('Scope 28 high equivalence', '301/301 PASS'), ('Scope 29 pre-live parity', '8/8 PASS'), ('Tracker profile', 'bytetrack_motion_adaptive'), ('V3 TEST accessed', False), ('Actuator enabled', False)])}

The frozen detector, Scope 28 dual-stream adapter, and tracker config were verified before the camera run. No production package or TEST artifact was modified.
""",
        "SCOPE29_CAMERA_DISCOVERY.md": f"""# Scope 29 — Camera Discovery

{table([('Selected capture device', '/dev/video0'), ('USB identity', camera['identity']), ('Vendor/Product', f"{camera['vendor_id']}:{camera['product_id']}"), ('Metadata node', '/dev/video1'), ('Pi model', 'Raspberry Pi 5 Model B Rev 1.0'), ('Architecture', 'aarch64'), ('OpenCV', '5.0.0'), ('v4l2-ctl', 'available'), ('Camera stream probe', 'blocked/hung after repeated long runs')])}

`/dev/video0` is the USB capture node; `/dev/video1` is metadata-only. The camera advertises MJPG 640x480 at 25/30 FPS and YUYV 640x480 at 30 FPS. Raw discovery is in `.runtime/scope29/camera_discovery_raw.txt`.

The latest read-only V4L2 probe did not complete 100 frames within 20 seconds. No user process held `/dev/video0`; the safe next action is to reconnect/power-cycle the webcam.
""",
        "SCOPE29_CAMERA_CONTRACT.md": """# Scope 29 — Camera Contract

Selected mode: `/dev/video0`, MJPG, 640x480, requested 25 FPS. This is a source-frame contract; NCNN still receives BGR -> RGB, rect=False LetterBox, padding 114, 480x480, float32/255, NCHW.

Scope 28 dual stream is unchanged: public HIGH >=0.25, tracker LOW 0.10–<0.25, one inference and one NMS at IoU 0.70. Tracker profile/config remains `bytetrack_motion_adaptive`.

Capture uses a bounded queue of size 1 with `drop_stale_keep_newest`; all queue drops, read failures, and invalid dimensions are counted.
""",
        "SCOPE29_LIVE_PIPELINE.md": """# Scope 29 — Live Pipeline

Run-by-command only, headless log-only mode:

`python scope29_pi_live.py --config smoke_config.json --mode smoke`

Capture thread -> bounded latest-frame queue -> frozen NCNN/Scope 28 dual stream -> existing ByteTrack -> target preview -> JSONL state log. No GUI, service, cron, autostart, upload, or cloud path is created.

Per-frame logs include capture monotonic timestamp, source resolution, HIGH/LOW detections, track IDs, target state, stage latencies, capture-to-result age, and actuator-disabled preview.
""",
        "SCOPE29_LIVE_SMOKE.md": f"""# Scope 29 — Live Smoke

Preliminary accepted smoke (25 FPS mode, before final telemetry/frame guards): 45.05 seconds, 1155 captured, 991 processed, 163 stale queue drops, 0 read failures, source 640x480, processing mean 45.06 ms, no actuation.

Latest rerun after final guards was blocked by camera runtime state after 22.44 seconds with five consecutive read failures. It is recorded in `.runtime/scope29/smoke_summary.json`; it is not treated as a PASS.

The fixed 8-image pre-live HIGH parity gate remained `8/8 PASS`.
""",
        "SCOPE29_TRACKING_RESULTS.md": """# Scope 29 — Tracking Results

The webcam scene contained no detections during the accepted smoke evidence, so no track ID or target-state characterization can be claimed for a drone target. Rows correctly report `NONE`; this is not converted into a detector/tracker quality metric.

The live state log schema and Scope 28 association source labeling are present. No tracker thresholds or profile were changed.
""",
        "SCOPE29_PI_PERFORMANCE.md": f"""# Scope 29 — Pi Performance

Accepted preliminary smoke at 640x480 MJPG: processing mean 45.06 ms; camera cadence about 25.76 FPS; processing about 22.00 FPS; peak RSS 145,376 KB; temperature 45.0 -> 52.7 C; throttling 0x0 -> 0x0.

Rejected sustained attempts:

{table([('30 FPS attempt', '500.2 s; 12,872 captured; 5 read failures; rejected'), ('25 FPS unbounded telemetry', '600.1 s; 15,453 captured; telemetry memory accumulation; rejected'), ('25 FPS bounded telemetry', '600.1 s; RSS bounded but invalid decoded source dimensions; rejected'), ('25 FPS frame-copy', '600.2 s; RSS bounded but 4 invalid decoded source dimensions; rejected'), ('Final guard rerun', 'camera runtime blocked during smoke; no final sustained run')])}

The factual performance numbers from rejected attempts are diagnostic only, not a stable live deployment claim.
""",
        "SCOPE29_SUSTAINED_RUN.md": f"""# Scope 29 — Sustained Run

Final sustained status: `CAMERA_RUNTIME_BLOCKED`.

Multiple 10-minute runs were attempted. One 25 FPS run reached 600 seconds with no read failures, but telemetry/source-buffer defects were found and corrected; subsequent validation exposed intermittent invalid decoded dimensions, then the camera entered a runtime state where even the final smoke could not maintain capture. The final run is not marked PASS.

User action required: reconnect or power-cycle the USB webcam, verify a short `v4l2-ctl` stream on `/dev/video0`, then rerun Scope 29. No system reset or automatic USB workaround was performed.
""",
        "SCOPE29_FAILURE_HANDLING.md": f"""# Scope 29 — Failure Handling

- Invalid device `/dev/video999`: clean `CAMERA_OPEN_FAILED`, non-zero exit, model not loaded, actuator disabled.
- Consecutive camera read failures: bounded retry, `FRAME_READ_FAILED`, camera release, no stale target continuation, no actuator output.
- Invalid decoded frame dimensions: rejected and counted as `invalid_frame_dimensions`, never sent to detector/tracker.
- No uncontrolled retry loop, service, or autostart.

Latest blocker: V4L2 stream probe did not complete 100 frames within 20 seconds and requires webcam reconnect/power-cycle.
""",
        "SCOPE29_DRYRUN_SAFETY.md": """# Scope 29 — Dry-Run Safety

All runs use `DRY_RUN_ONLY`; GPIO/PWM/serial writes are zero. No servo, motor, live targeting, webcam upload, display service, or autostart was enabled. Target error preview remains software-only.
""",
        "SCOPE29_TEST_REPORT.md": """# Scope 29 — Test Report

Pre-live parity: 8/8 PASS; max confidence difference 0.001234353; minimum bbox IoU 0.971743339; one inference and one NMS per image.

Invalid-camera safety test: PASS (`CAMERA_OPEN_FAILED`, model not loaded, actuator disabled). Full regression/compile/diff-check are reported after the final harness fixes. Scope 25/26 hashes remain unchanged and V3 TEST was not accessed.

The implementation underwent bounded-telemetry, frame-ownership, and invalid-frame guards after rejected sustained diagnostics. Those rejected artifacts are preserved and explicitly labeled.
""",
        "SCOPE29_FINAL_REPORT.md": f"""# Scope 29 — Final Report

Final status: `{run_status}`

{table([('USB camera/device', '/dev/video0 — Jieli Technology USB Composite Device'), ('Selected format/resolution/FPS', 'MJPG, 640x480, requested 25 FPS'), ('Parity smoke', '8/8 PASS; max conf diff %.9f; min bbox IoU %.9f' % (max_conf, min_iou)), ('Accepted short smoke', '45.05 s preliminary evidence; 1155 captured / 991 processed / 163 stale drops'), ('Final sustained run', 'Not accepted; camera runtime became unstable/blocked after corrective iterations'), ('Frozen detector hashes', 'UNCHANGED'), ('Scope 28 dual stream', 'RETAINED'), ('Scope 26 headline', 'UNCHANGED'), ('Physical writes', '0 GPIO / 0 PWM / 0 serial'), ('Autostart', 'None'), ('V3 TEST', 'Not accessed')])}

The live integration code is implemented with bounded queue, explicit drop accounting, monotonic timestamps, source-frame validation, one NCNN inference/one NMS, Scope 28 HIGH/LOW streams, and dry-run target preview. However, the final live gate cannot be called READY because the USB camera did not remain reliable through the final validation sequence; V4L2 streaming also failed to complete a short probe. No model, tracker, threshold, or test artifact was changed to compensate.

Required user action: reconnect or power-cycle the USB webcam and rerun the Scope 29 command. Do not start Scope 30 automatically.
""",
    }
    for name, content in docs.items(): write(DOCS / name, content)
    print(json.dumps({"status": run_status, "docs": sorted(docs), "artifact_manifest_sha256": sha256(ARTIFACTS / "ARTIFACT_MANIFEST.json")}, indent=2))


if __name__ == "__main__":
    main()
