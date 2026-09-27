#!/usr/bin/env python3
"""Scope 29 baseline gate before any live camera capture."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope29"
PACKAGE = ROOT / "artifacts/production-candidate/scope25"
EXPECTED = {
    "freeze_manifest": "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964",
    "headline": "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83",
    "param": "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5",
    "bin": "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    actual = {
        "freeze_manifest": sha256(ROOT / ".runtime/scope25/scope25_freeze_manifest.json"),
        "headline": sha256(ROOT / ".runtime/scope26/headline_result.json"),
        "param": sha256(PACKAGE / "model.ncnn.param"),
        "bin": sha256(PACKAGE / "model.ncnn.bin"),
    }
    if actual != EXPECTED:
        raise SystemExit("SCOPE29_BASELINE_MISMATCH")
    scope28 = json.loads((ROOT / ".runtime/scope28/summary.json").read_text())
    parity = json.loads((ROOT / ".runtime/scope28/parity_8.json").read_text())
    if scope28["status"] != "DRY_RUN_COMPLETE" or parity["status"] != "PARITY_PASS" or scope28["high_stream_equivalence"]["fail_frames"] != 0:
        raise SystemExit("SCOPE28_BASELINE_NOT_ACCEPTED")
    audit = {
        "status": "INPUTS_VERIFIED",
        "candidate_id": "scope18-yolov8n-480:ncnn",
        "detector": {"backend": "NCNN", "precision": "FP32", "imgsz": 480, "public_confidence": 0.25, "tracker_floor": 0.10, "nms_iou": 0.70, "param_sha256": actual["param"], "bin_sha256": actual["bin"]},
        "tracker_profile": "bytetrack_motion_adaptive",
        "scope28_status": scope28["status"],
        "scope28_high_equivalence": scope28["high_stream_equivalence"],
        "scope28_parity_8": parity["status"],
        "freeze_manifest_sha256": actual["freeze_manifest"],
        "scope26_headline_sha256": actual["headline"],
        "v3_test_used_for_tuning": False,
        "webcam_capture_started": False,
        "actuator_output_enabled": False,
        "camera_mode_policy": {"requested_device": "/dev/video0", "pixel_format": "MJPG", "width": 640, "height": 480, "fps_request": 25, "queue_size": 1, "drop_policy": "drop_stale_keep_newest"},
    }
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
