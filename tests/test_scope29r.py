"""Scope 29R post-power-cycle recovery and live-camera acceptance guards."""
from __future__ import annotations

import hashlib
import json
import ast
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope29r"
FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name: str):
    return json.loads((RUNTIME / name).read_text())


def test_scope29r_baselines_and_v4l2_probe_are_locked():
    assert digest(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == FREEZE
    assert digest(ROOT / ".runtime/scope26/headline_result.json") == HEADLINE
    assert digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == PARAM
    assert digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == BIN
    assert "V4L2_PROBE_EXIT:0" in (RUNTIME / "v4l2_probe_stdout.log").read_text()


def test_scope29r_parity_and_invalid_camera_safety():
    parity = read("parity_8.json")
    invalid = read("invalid_camera_summary.json")
    assert parity["status"] == "PARITY_PASS"
    assert len(parity["images"]) == 8
    assert all(row["comparison"]["status"] == "PARITY_PASS" for row in parity["images"])
    assert all(row["contract"]["nms_applications"] == 1 for row in parity["images"])
    assert invalid == {
        "status": "CAMERA_OPEN_FAILED",
        "camera": {"device": "/dev/video999"},
        "actuator": {"mode": "DRY_RUN_ONLY", "enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0},
        "model_loaded": False,
    }


def test_scope29r_smoke_and_sustained_gates():
    smoke = read("smoke_summary.json")
    sustained = read("sustained_summary.json")
    assert smoke["status"] == "LIVE_SMOKE_COMPLETE"
    assert smoke["duration_wall_s"] >= 60
    assert smoke["frames_dropped"]["capture_read_failures"] == 0
    assert smoke["frames_dropped"]["invalid_frame_dimensions"] == 0
    assert sustained["status"] == "LIVE_SUSTAINED_COMPLETE"
    assert sustained["duration_wall_s"] >= 600
    assert sustained["frames_dropped"]["capture_read_failures"] == 0
    assert sustained["frames_dropped"]["invalid_frame_dimensions"] == 0
    assert sustained["camera"]["source_resolution"] == [[640, 480]]
    for metric in sustained["latency_ms"].values():
        assert metric["sample_count"] <= 2048
        assert metric["sample_policy"] == "bounded_rolling_2048"


def test_scope29r_every_sustained_row_has_fixed_source_resolution_and_no_actuation():
    rows = [json.loads(line) for line in (RUNTIME / "sustained_live_state.jsonl").read_text().splitlines()]
    assert rows
    assert all(row["source_resolution"] == [640, 480] for row in rows)
    assert all(row["actuator_output_enabled"] is False for row in rows)
    assert all(row["command_preview"]["gpio_write"] is False for row in rows)
    assert all(row["command_preview"]["pwm_write"] is False for row in rows)
    assert all(row["command_preview"]["serial_write"] is False for row in rows)


def test_scope29r_capture_shape_guard():
    module = ast.parse((ROOT / "scripts/scope29_pi_live.py").read_text())
    function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "valid_capture_frame")
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "scope29_pi_live.py", "exec"), namespace)
    valid_capture_frame = namespace["valid_capture_frame"]

    assert not valid_capture_frame(None, 640, 480)
    assert not valid_capture_frame(np.zeros((480, 640), dtype=np.uint8), 640, 480)
    assert not valid_capture_frame(np.zeros((480, 640, 4), dtype=np.uint8), 640, 480)
    assert valid_capture_frame(np.zeros((480, 640, 3), dtype=np.uint8), 640, 480)


def test_scope29r_final_status_has_no_test_access_or_autostart():
    final = read("final_status.json")
    assert final["status"] == "USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY"
    assert final["gate"]["test_accessed"] is False
    assert final["no_servo_gpio_pwm_serial"] is True
    assert final["no_autostart"] is True
    assert final["target_presence_smoke"].startswith("NOT_PERFORMED")
    assert not (ROOT / "artifacts/integration/scope29/autostart.service").exists()
