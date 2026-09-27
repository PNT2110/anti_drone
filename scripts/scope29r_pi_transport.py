#!/usr/bin/env python3
"""Scope 29R post-power-cycle gate and final corrected live validation."""
from __future__ import annotations

import json
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope29r"
PACKAGE = ROOT / "artifacts/production-candidate/scope25"
REMOTE = "/home/pitan/antidrone-scope29r-live"


def run(client, command, timeout=900):
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode(errors="replace"); err = stderr.read().decode(errors="replace"); code = stdout.channel.recv_exit_status()
    return code, out, err


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    audit = json.loads((ROOT / ".runtime/scope29/input_audit.json").read_text())
    if audit["freeze_manifest_sha256"] != "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964" or audit["scope26_headline_sha256"] != "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83":
        raise SystemExit("SCOPE29R_BASELINE_MISMATCH")
    benchmark = json.loads((ROOT / ".runtime/scope19/benchmark_input_manifest.json").read_text())
    config = {"candidate_id": "scope18-yolov8n-480:ncnn", "model_dir": f"{REMOTE}/model", "input_root": f"{REMOTE}/inputs", "reference": f"{REMOTE}/host_reference.json", "run_id": "scope18-yolov8n-480", "output": f"{REMOTE}/parity_8.json", "images": [{"filename": Path(path).name} for path in benchmark["paths"]], "param_sha256": "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5", "bin_sha256": "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"}
    tracker_config = {"detector_confidence_floor": 0.10, "track_low_thresh": 0.10, "track_high_thresh": 0.25, "new_track_thresh": 0.35, "match_iou": 0.30, "adaptive_center_gate": 2.50, "adaptive_mahalanobis_gate": 25.0, "process_noise": 1.0, "measurement_noise": 4.0, "min_confirmed_observations": 2, "max_lost_seconds": 0.60, "max_gap_before_reset_seconds": 1.00}
    live_base = {"model_dir": f"{REMOTE}/model", "device": "/dev/video0", "width": 640, "height": 480, "fps": 25, "param_sha256": config["param_sha256"], "bin_sha256": config["bin_sha256"], "tracker_config": tracker_config, "output_dir": f"{REMOTE}/output_smoke"}
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy()); client.connect("192.168.1.118", username="pitan", password="1234", look_for_keys=False, allow_agent=False, timeout=10, auth_timeout=10, banner_timeout=10)
    try:
        discover = "lsusb; v4l2-ctl --list-devices; ls -l /dev/video*; uname -a; uname -m; cat /proc/device-tree/model; free -h; python3 --version; /home/pitan/antidrone-scope21/venv/bin/python -c 'import cv2; print(\"opencv\",cv2.__version__)'; v4l2-ctl -d /dev/video0 --list-formats-ext; udevadm info --query=property --name=/dev/video0 2>/dev/null | grep -E 'ID_VENDOR=|ID_MODEL=|ID_SERIAL=|DEVNAME=' || true"
        code, out, err = run(client, discover, timeout=60); (RUNTIME / "camera_discovery_raw.txt").write_text(out + "\nSTDERR:\n" + err)
        if code != 0: raise SystemExit("CAMERA_DISCOVERY_FAILED")
        probe = "timeout 60s v4l2-ctl -d /dev/video0 --set-fmt-video=width=640,height=480,pixelformat=MJPG --set-parm=25 --stream-mmap --stream-count=250 --stream-to=/dev/null; echo V4L2_PROBE_EXIT:$?"
        code, out, err = run(client, probe, timeout=75); (RUNTIME / "v4l2_probe_stdout.log").write_text(out); (RUNTIME / "v4l2_probe_stderr.log").write_text(err)
        if code != 0 or "V4L2_PROBE_EXIT:0" not in out: raise SystemExit("CAMERA_V4L2_BLOCKED")
        _, out, err = run(client, f"mkdir -p {REMOTE}/model {REMOTE}/inputs {REMOTE}/src/anti_drone/tracking {REMOTE}/output_smoke {REMOTE}/output_sustained {REMOTE}/output_invalid", timeout=30)
        sftp = client.open_sftp()
        files = [(PACKAGE / "model.ncnn.param", f"{REMOTE}/model/model.ncnn.param"), (PACKAGE / "model.ncnn.bin", f"{REMOTE}/model/model.ncnn.bin"), (ROOT / "scripts/scope21_pi_runner.py", f"{REMOTE}/scope21_pi_runner.py"), (ROOT / "scripts/scope28_pi_runner.py", f"{REMOTE}/scope28_pi_runner.py"), (ROOT / "scripts/scope29_pi_parity_runner.py", f"{REMOTE}/scope29_pi_parity_runner.py"), (ROOT / "scripts/scope29_pi_live.py", f"{REMOTE}/scope29_pi_live.py"), (ROOT / ".runtime/scope25/host_reference.json", f"{REMOTE}/host_reference.json")]
        for local, remote in files: sftp.put(str(local), remote)
        sftp.put(str(ROOT / "src/anti_drone/__init__.py"), f"{REMOTE}/src/anti_drone/__init__.py"); sftp.put(str(ROOT / "src/anti_drone/scope28_contract.py"), f"{REMOTE}/src/anti_drone/scope28_contract.py")
        for local in sorted((ROOT / "src/anti_drone/tracking").glob("*.py")): sftp.put(str(local), f"{REMOTE}/src/anti_drone/tracking/{local.name}")
        for path in benchmark["paths"]:
            local = Path(path); sftp.put(str(local), f"{REMOTE}/inputs/{local.name}")
        (RUNTIME / "parity_config.json").write_text(json.dumps(config, indent=2) + "\n"); sftp.put(str(RUNTIME / "parity_config.json"), f"{REMOTE}/config.json")
        sftp.close()
        code, out, err = run(client, f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope29_pi_parity_runner.py", timeout=300); (RUNTIME / "parity_stdout.log").write_text(out); (RUNTIME / "parity_stderr.log").write_text(err)
        if code != 0: raise SystemExit("DETECTOR_REGRESSION")
        sftp = client.open_sftp(); sftp.get(f"{REMOTE}/parity_8.json", str(RUNTIME / "parity_8.json")); sftp.close()
        if json.loads((RUNTIME / "parity_8.json").read_text())["status"] != "PARITY_PASS": raise SystemExit("DETECTOR_REGRESSION")

        invalid = dict(live_base); invalid.update({"device": "/dev/video999", "duration_s": 1, "output_dir": f"{REMOTE}/output_invalid"}); (RUNTIME / "invalid_camera_config.json").write_text(json.dumps(invalid, indent=2) + "\n")
        sftp = client.open_sftp(); sftp.put(str(RUNTIME / "invalid_camera_config.json"), f"{REMOTE}/invalid_camera_config.json"); sftp.close()
        code, out, err = run(client, f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope29_pi_live.py --config invalid_camera_config.json --mode smoke", timeout=30); (RUNTIME / "invalid_camera_stdout.log").write_text(out); (RUNTIME / "invalid_camera_stderr.log").write_text(err)
        sftp = client.open_sftp(); sftp.get(f"{REMOTE}/output_invalid/summary.json", str(RUNTIME / "invalid_camera_summary.json")); sftp.close()
        if json.loads((RUNTIME / "invalid_camera_summary.json").read_text())["status"] != "CAMERA_OPEN_FAILED": raise SystemExit("CAMERA_FAILURE_GUARD_FAIL")

        smoke = dict(live_base); smoke.update({"duration_s": 60, "output_dir": f"{REMOTE}/output_smoke"}); (RUNTIME / "smoke_config.json").write_text(json.dumps(smoke, indent=2) + "\n")
        sftp = client.open_sftp(); sftp.put(str(RUNTIME / "smoke_config.json"), f"{REMOTE}/smoke_config.json"); sftp.close()
        code, out, err = run(client, f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope29_pi_live.py --config smoke_config.json --mode smoke", timeout=180); (RUNTIME / "smoke_stdout.log").write_text(out); (RUNTIME / "smoke_stderr.log").write_text(err)
        if code != 0: raise SystemExit("FINAL_SMOKE_FAILED")
        sftp = client.open_sftp(); sftp.get(f"{REMOTE}/output_smoke/summary.json", str(RUNTIME / "smoke_summary.json")); sftp.get(f"{REMOTE}/output_smoke/live_state.jsonl", str(RUNTIME / "smoke_live_state.jsonl")); sftp.close()
        smoke_result = json.loads((RUNTIME / "smoke_summary.json").read_text())
        if smoke_result["status"] != "LIVE_SMOKE_COMPLETE" or smoke_result["frames_dropped"]["capture_read_failures"] or smoke_result["frames_dropped"]["invalid_frame_dimensions"]: raise SystemExit("FINAL_SMOKE_FAILED")

        sustained = dict(live_base); sustained.update({"duration_s": 600, "output_dir": f"{REMOTE}/output_sustained"}); (RUNTIME / "sustained_config.json").write_text(json.dumps(sustained, indent=2) + "\n")
        sftp = client.open_sftp(); sftp.put(str(RUNTIME / "sustained_config.json"), f"{REMOTE}/sustained_config.json"); sftp.close()
        code, out, err = run(client, f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope29_pi_live.py --config sustained_config.json --mode sustained", timeout=750); (RUNTIME / "sustained_stdout.log").write_text(out); (RUNTIME / "sustained_stderr.log").write_text(err)
        if code != 0: raise SystemExit("SUSTAINED_RUN_FAILED")
        sftp = client.open_sftp(); sftp.get(f"{REMOTE}/output_sustained/summary.json", str(RUNTIME / "sustained_summary.json")); sftp.get(f"{REMOTE}/output_sustained/live_state.jsonl", str(RUNTIME / "sustained_live_state.jsonl")); sftp.close()
        result = json.loads((RUNTIME / "sustained_summary.json").read_text())
        if result["status"] != "LIVE_SUSTAINED_COMPLETE" or result["duration_wall_s"] < 600 or result["frames_dropped"]["capture_read_failures"] or result["frames_dropped"]["invalid_frame_dimensions"]: raise SystemExit("SUSTAINED_RUN_FAILED")
        print(json.dumps({"status": "CAMERA_RUNTIME_RECOVERED", "v4l2_probe": "PASS_250_FRAMES", "smoke": json.loads((RUNTIME / "smoke_summary.json").read_text()), "sustained": result}, indent=2))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
