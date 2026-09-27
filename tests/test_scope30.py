"""Scope 30 command-preview and live-target safety guards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope30"
FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope30_frozen_baselines_and_scope29r_closeout():
    assert digest(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == FREEZE
    assert digest(ROOT / ".runtime/scope26/headline_result.json") == HEADLINE
    assert digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == PARAM
    assert digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == BIN
    final = json.loads((ROOT / ".runtime/scope29r/final_status.json").read_text())
    assert final["status"] == "USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY"
    assert final["gate"]["test_accessed"] is False
    assert "Scope 29R recovery" in (ROOT / "docs/tracking/scope29/SCOPE29_INPUT_AUDIT.md").read_text()


def test_scope30_frame_center_and_normalized_error():
    from anti_drone.scope30_command_preview import frame_center, normalized_error

    assert frame_center(640, 480) == (320.0, 240.0)
    assert normalized_error((320, 240), 640, 480) == (0.0, 0.0)
    assert normalized_error((0, 0), 640, 480) == (-1.0, -1.0)
    assert normalized_error((640, 480), 640, 480) == (1.0, 1.0)


def test_scope30_preview_bounds_rate_limit_and_states():
    from anti_drone.scope30_command_preview import CommandPreview

    preview = CommandPreview()
    observed = preview.preview(target_state="HIGH_OBSERVED", target_center=(640, 480), frame_width=640, frame_height=480)
    assert observed["state"] == "TRACKING"
    assert observed["error_x_norm"] == 1.0 and observed["error_y_norm"] == 1.0
    assert observed["rate_limited_pan"] == 0.25
    assert observed["rate_limited_tilt"] == 0.25
    assert observed["actuator_output_enabled"] is False
    assert observed["gpio_write"] is False and observed["pwm_write"] is False and observed["serial_write"] is False
    predicted = preview.preview(target_state="PREDICTED", target_center=(640, 480), frame_width=640, frame_height=480)
    assert predicted["state"] == "HOLD_PREVIEW"
    lost = preview.preview(target_state="NONE", target_center=None, frame_width=640, frame_height=480)
    assert lost["state"] == "RETURN_NEUTRAL_PREVIEW"
    for _ in range(8):
        lost = preview.preview(target_state="NONE", target_center=None, frame_width=640, frame_height=480)
    assert lost["state"] == "NO_TARGET"
    assert lost["rate_limited_pan"] == 0.0 and lost["rate_limited_tilt"] == 0.0


def test_scope30_camera_failure_is_safe_and_no_hardware_sink_is_imported():
    from anti_drone.scope30_command_preview import CommandPreview

    safe = CommandPreview().preview(target_state="HIGH_OBSERVED", target_center=(600, 300), frame_width=640, frame_height=480, camera_failed=True)
    assert safe["state"] == "SAFE_NO_TARGET"
    assert safe["rate_limited_pan"] == 0.0 and safe["rate_limited_tilt"] == 0.0
    source = (ROOT / "scripts/scope30_pi_live_target.py").read_text()
    assert "RPi.GPIO" not in source and "serial.Serial" not in source and "PWM" not in source
    assert "DRY_RUN_ONLY" in source
    assert not (ROOT / "artifacts/integration/scope30/autostart.service").exists()


def test_scope30_tracker_profile_and_thresholds_are_unchanged():
    config = (ROOT / "configs/trackers/bytetrack_motion_adaptive.yaml").read_text()
    assert "name: bytetrack_motion_adaptive" in config
    assert "track_low_thresh: 0.10" in config
    assert "track_high_thresh: 0.25" in config
    assert "new_track_thresh: 0.35" in config
    assert "nms" not in config.lower()


def test_scope30_live_target_artifact_when_available():
    summary_path = RUNTIME / "target_summary.json"
    if not summary_path.exists():
        pytest.skip("live target session has not been collected yet")
    summary = json.loads(summary_path.read_text())
    assert summary["test_accessed"] is False
    assert summary["actuator"]["enabled"] is False
    assert summary["detector"]["public_threshold"] == 0.25
    assert summary["detector"]["tracker_floor"] == 0.10
    assert summary["detector"]["nms_iou"] == 0.70
    assert summary["tracker_profile"] == "bytetrack_motion_adaptive"
