#!/usr/bin/env python3
"""Run Scope 30 on the physical Pi webcam; never initializes an actuator."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope30"
PACKAGE = ROOT / "artifacts/production-candidate/scope25"
REMOTE = "/home/pitan/antidrone-scope30-live"
FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(client, command: str, timeout: int = 120):
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if digest(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") != FREEZE or digest(ROOT / ".runtime/scope26/headline_result.json") != HEADLINE:
        raise SystemExit("SCOPE30_BASELINE_MISMATCH")
    if digest(PACKAGE / "model.ncnn.param") != PARAM or digest(PACKAGE / "model.ncnn.bin") != BIN:
        raise SystemExit("SCOPE30_PACKAGE_MISMATCH")

    tracker_config = {"detector_confidence_floor": 0.10, "track_low_thresh": 0.10, "track_high_thresh": 0.25, "new_track_thresh": 0.35, "match_iou": 0.30, "adaptive_center_gate": 2.50, "adaptive_mahalanobis_gate": 25.0, "process_noise": 1.0, "measurement_noise": 4.0, "min_confirmed_observations": 2, "max_lost_seconds": 0.60, "max_gap_before_reset_seconds": 1.00}
    config = {"model_dir": f"{REMOTE}/model", "device": "/dev/video0", "width": 640, "height": 480, "fps": 25, "param_sha256": PARAM, "bin_sha256": BIN, "tracker_config": tracker_config, "preview_envelope": {"neutral": 0.0, "minimum": -1.0, "maximum": 1.0, "max_delta_per_frame": 0.25}, "duration_s": 90, "output_dir": f"{REMOTE}/target_output", "target_source": {"type": "screen_presented_diagnostic_video", "video": "Halmstad V_DRONE_001.mp4", "video_frames": 301, "video_fps": 30.0, "monitor_resolution": "2560x1440 HDMI-1 host display (observed by xrandr)", "camera_to_screen_setup": "physical USB webcam pointed at host monitor; approximate distance not instrumented", "pipeline_input": "physical USB webcam /dev/video0; video file is not passed to detector"}}
    invalid = dict(config); invalid.update({"device": "/dev/video999", "duration_s": 1, "output_dir": f"{REMOTE}/invalid_output"})
    (RUNTIME / "target_config.json").write_text(json.dumps(config, indent=2) + "\n")
    (RUNTIME / "invalid_camera_config.json").write_text(json.dumps(invalid, indent=2) + "\n")

    password = os.environ.get("SCOPE30_PI_PASSWORD")
    if not password:
        raise SystemExit("SCOPE30_PI_PASSWORD_REQUIRED")
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(os.environ.get("SCOPE30_PI_HOST", "192.168.1.118"), username=os.environ.get("SCOPE30_PI_USER", "pitan"), password=password, look_for_keys=False, allow_agent=False, timeout=10, auth_timeout=10, banner_timeout=10)
    try:
        code, out, err = run(client, "lsusb; v4l2-ctl --list-devices; ls -l /dev/video*; uname -a; uname -m; cat /proc/device-tree/model; free -h; /home/pitan/antidrone-scope21/venv/bin/python -c 'import cv2; print(\"opencv\", cv2.__version__)'; v4l2-ctl -d /dev/video0 --list-formats-ext", 60)
        (RUNTIME / "camera_discovery_raw.txt").write_text(out + "\nSTDERR:\n" + err)
        if code != 0:
            raise SystemExit("CAMERA_DISCOVERY_FAILED")
        code, out, err = run(client, "timeout 30s v4l2-ctl -d /dev/video0 --set-fmt-video=width=640,height=480,pixelformat=MJPG --set-parm=25 --stream-mmap --stream-count=60 --stream-to=/dev/null; echo V4L2_PROBE_EXIT:$?", 45)
        (RUNTIME / "v4l2_probe_stdout.log").write_text(out); (RUNTIME / "v4l2_probe_stderr.log").write_text(err)
        if code != 0 or "V4L2_PROBE_EXIT:0" not in out:
            raise SystemExit("CAMERA_RUNTIME_REGRESSION")

        run(client, f"mkdir -p {REMOTE}/model {REMOTE}/src/anti_drone/tracking {REMOTE}/target_output {REMOTE}/invalid_output", 30)
        sftp = client.open_sftp()
        files = [(PACKAGE / "model.ncnn.param", f"{REMOTE}/model/model.ncnn.param"), (PACKAGE / "model.ncnn.bin", f"{REMOTE}/model/model.ncnn.bin"), (ROOT / "scripts/scope21_pi_runner.py", f"{REMOTE}/scope21_pi_runner.py"), (ROOT / "scripts/scope28_pi_runner.py", f"{REMOTE}/scope28_pi_runner.py"), (ROOT / "scripts/scope29_pi_live.py", f"{REMOTE}/scope29_pi_live.py"), (ROOT / "scripts/scope30_pi_live_target.py", f"{REMOTE}/scope30_pi_live_target.py"), (ROOT / "src/anti_drone/scope28_contract.py", f"{REMOTE}/src/anti_drone/scope28_contract.py"), (ROOT / "src/anti_drone/scope30_command_preview.py", f"{REMOTE}/src/anti_drone/scope30_command_preview.py"), (ROOT / "src/anti_drone/__init__.py", f"{REMOTE}/src/anti_drone/__init__.py")]
        for local, remote in files:
            sftp.put(str(local), remote)
        for local in sorted((ROOT / "src/anti_drone/tracking").glob("*.py")):
            sftp.put(str(local), f"{REMOTE}/src/anti_drone/tracking/{local.name}")
        sftp.put(str(RUNTIME / "target_config.json"), f"{REMOTE}/target_config.json")
        sftp.put(str(RUNTIME / "invalid_camera_config.json"), f"{REMOTE}/invalid_camera_config.json")
        sftp.close()

        code, out, err = run(client, f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope30_pi_live_target.py --config invalid_camera_config.json", 30)
        (RUNTIME / "invalid_camera_stdout.log").write_text(out); (RUNTIME / "invalid_camera_stderr.log").write_text(err)
        sftp = client.open_sftp(); sftp.get(f"{REMOTE}/invalid_output/summary.json", str(RUNTIME / "invalid_camera_summary.json")); sftp.close()
        invalid_result = json.loads((RUNTIME / "invalid_camera_summary.json").read_text())
        if invalid_result.get("status") != "CAMERA_OPEN_FAILED":
            raise SystemExit("CAMERA_FAILURE_GUARD_FAIL")

        code, out, err = run(client, f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope30_pi_live_target.py --config target_config.json", 150)
        (RUNTIME / "target_stdout.log").write_text(out); (RUNTIME / "target_stderr.log").write_text(err)
        sftp = client.open_sftp(); sftp.get(f"{REMOTE}/target_output/summary.json", str(RUNTIME / "target_summary.json")); sftp.get(f"{REMOTE}/target_output/target_state.jsonl", str(RUNTIME / "target_state.jsonl")); sftp.close()
        result = json.loads((RUNTIME / "target_summary.json").read_text())
        print(json.dumps({"transport": "COMPLETE", "camera_probe": "PASS_60_FRAMES", "target_exit_code": code, "target_status": result.get("status"), "target_seen": result.get("target_seen"), "frames_processed": result.get("frames_processed"), "track_ids": result.get("track_ids_created")}, indent=2))
        return 0 if code == 0 and result.get("target_seen") else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
