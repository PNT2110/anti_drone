#!/usr/bin/env python3
"""Scope 29 Pi transfer, parity gate, live smoke, and sustained run."""
from __future__ import annotations

import json
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope29"
PACKAGE = ROOT / "artifacts/production-candidate/scope25"
REMOTE = "/home/pitan/antidrone-scope29-live"


def run(client, command, timeout=900):
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode(errors="replace"); err = stderr.read().decode(errors="replace"); code = stdout.channel.recv_exit_status()
    return code, out, err


def main() -> int:
    audit = json.loads((RUNTIME / "input_audit.json").read_text())
    if audit["scope28_parity_8"] != "PARITY_PASS" or audit["scope28_high_equivalence"]["fail_frames"] != 0:
        raise SystemExit("SCOPE29_BASELINE_NOT_ACCEPTED")
    benchmark = json.loads((ROOT / ".runtime/scope19/benchmark_input_manifest.json").read_text())
    config = {"candidate_id": audit["candidate_id"], "model_dir": f"{REMOTE}/model", "input_root": f"{REMOTE}/inputs", "reference": f"{REMOTE}/host_reference.json", "run_id": "scope18-yolov8n-480", "output": f"{REMOTE}/parity_8.json", "images": [{"filename": Path(path).name} for path in benchmark["paths"]], "param_sha256": audit["detector"]["param_sha256"], "bin_sha256": audit["detector"]["bin_sha256"]}
    live_base = {"model_dir": f"{REMOTE}/model", "device": "/dev/video0", "width": 640, "height": 480, "fps": 25, "param_sha256": audit["detector"]["param_sha256"], "bin_sha256": audit["detector"]["bin_sha256"], "tracker_config": {"detector_confidence_floor": 0.10, "track_low_thresh": 0.10, "track_high_thresh": 0.25, "new_track_thresh": 0.35, "match_iou": 0.30, "adaptive_center_gate": 2.50, "adaptive_mahalanobis_gate": 25.0, "process_noise": 1.0, "measurement_noise": 4.0, "min_confirmed_observations": 2, "max_lost_seconds": 0.60, "max_gap_before_reset_seconds": 1.00}, "output_dir": f"{REMOTE}/output_smoke"}
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy()); client.connect("192.168.1.118", username="pitan", password="1234", look_for_keys=False, allow_agent=False, timeout=10, auth_timeout=10, banner_timeout=10)
    try:
        discover_command = "uname -a; uname -m; cat /proc/device-tree/model; free -h; python3 --version; /home/pitan/antidrone-scope21/venv/bin/python -c 'import cv2; print(\"opencv\",cv2.__version__)'; command -v v4l2-ctl; v4l2-ctl --list-devices; for d in /dev/video0 /dev/video1; do echo DEVICE:$d; v4l2-ctl -d $d --list-formats-ext; udevadm info --query=property --name=$d 2>/dev/null | grep -E 'ID_VENDOR=|ID_MODEL=|ID_SERIAL=|DEVNAME=' || true; done"
        code, out, err = run(client, discover_command, timeout=60)
        (RUNTIME / "camera_discovery_raw.txt").write_text(out + "\nSTDERR:\n" + err)
        if code != 0:
            raise SystemExit("CAMERA_DISCOVERY_FAILED")
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
        code, out, err = run(client, f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope29_pi_parity_runner.py", timeout=300)
        (RUNTIME / "parity_stdout.log").write_text(out); (RUNTIME / "parity_stderr.log").write_text(err)
        if code != 0:
            raise SystemExit("SCOPE29_PARITY_FAIL")
        sftp = client.open_sftp(); sftp.get(f"{REMOTE}/parity_8.json", str(RUNTIME / "parity_8.json")); sftp.close()
        parity = json.loads((RUNTIME / "parity_8.json").read_text())
        if parity["status"] != "PARITY_PASS": raise SystemExit("SCOPE29_PARITY_FAIL")

        invalid = dict(live_base); invalid.update({"device": "/dev/video999", "duration_s": 1, "output_dir": f"{REMOTE}/output_invalid"}); (RUNTIME / "invalid_camera_config.json").write_text(json.dumps(invalid, indent=2) + "\n")
        sftp = client.open_sftp(); sftp.put(str(RUNTIME / "invalid_camera_config.json"), f"{REMOTE}/invalid_camera_config.json"); sftp.close()
        code, out, err = run(client, f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope29_pi_live.py --config invalid_camera_config.json --mode smoke", timeout=30)
        (RUNTIME / "invalid_camera_stdout.log").write_text(out); (RUNTIME / "invalid_camera_stderr.log").write_text(err)
        if code == 0: raise SystemExit("INVALID_CAMERA_TEST_UNEXPECTED_PASS")
        sftp = client.open_sftp(); sftp.get(f"{REMOTE}/output_invalid/summary.json", str(RUNTIME / "invalid_camera_summary.json")); sftp.close()

        smoke = dict(live_base); smoke.update({"duration_s": 45, "output_dir": f"{REMOTE}/output_smoke"}); (RUNTIME / "smoke_config.json").write_text(json.dumps(smoke, indent=2) + "\n")
        sftp = client.open_sftp(); sftp.put(str(RUNTIME / "smoke_config.json"), f"{REMOTE}/smoke_config.json"); sftp.close()
        code, out, err = run(client, f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope29_pi_live.py --config smoke_config.json --mode smoke", timeout=180)
        (RUNTIME / "smoke_stdout.log").write_text(out); (RUNTIME / "smoke_stderr.log").write_text(err)
        if code != 0: raise SystemExit("LIVE_SMOKE_FAILED")
        sftp = client.open_sftp(); sftp.get(f"{REMOTE}/output_smoke/summary.json", str(RUNTIME / "smoke_summary.json")); sftp.get(f"{REMOTE}/output_smoke/live_state.jsonl", str(RUNTIME / "smoke_live_state.jsonl")); sftp.close()
        smoke_result = json.loads((RUNTIME / "smoke_summary.json").read_text())
        if smoke_result["actuator"]["enabled"] or smoke_result["frames_processed"] == 0: raise SystemExit("LIVE_SMOKE_UNSAFE_OR_EMPTY")

        sustained = dict(live_base); sustained.update({"duration_s": 600, "output_dir": f"{REMOTE}/output_sustained"}); (RUNTIME / "sustained_config.json").write_text(json.dumps(sustained, indent=2) + "\n")
        sftp = client.open_sftp(); sftp.put(str(RUNTIME / "sustained_config.json"), f"{REMOTE}/sustained_config.json"); sftp.close()
        code, out, err = run(client, f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope29_pi_live.py --config sustained_config.json --mode sustained", timeout=750)
        (RUNTIME / "sustained_stdout.log").write_text(out); (RUNTIME / "sustained_stderr.log").write_text(err)
        if code != 0: raise SystemExit("LIVE_SUSTAINED_FAILED")
        sftp = client.open_sftp(); sftp.get(f"{REMOTE}/output_sustained/summary.json", str(RUNTIME / "sustained_summary.json")); sftp.get(f"{REMOTE}/output_sustained/live_state.jsonl", str(RUNTIME / "sustained_live_state.jsonl")); sftp.close()
        result = json.loads((RUNTIME / "sustained_summary.json").read_text())
        print(json.dumps({"status": result["status"], "frames_captured": result["frames_captured"], "frames_processed": result["frames_processed"], "drops": result["frames_dropped"], "capture_fps": result["fps"]["camera_capture_fps"], "processing_fps": result["fps"]["pipeline_processing_fps"], "latency": result["latency_ms"]["total_processing_ms"], "temperature": [result["hardware"].get("temperature_before"), result["hardware"].get("temperature_after")], "throttling": [result["hardware"].get("throttling_before"), result["hardware"].get("throttling_after")], "actuator": result["actuator"]}, indent=2))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
