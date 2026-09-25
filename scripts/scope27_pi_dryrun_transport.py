#!/usr/bin/env python3
"""Run Scope 27 offline dry-run in a separate Pi workspace."""
from __future__ import annotations

import json
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope27"
PACKAGE = ROOT / "artifacts/production-candidate/scope25"
REMOTE = "/home/pitan/antidrone-scope27-dryrun"


def main() -> int:
    audit = json.loads((RUNTIME / "input_audit.json").read_text())
    sequence = json.loads((RUNTIME / "sequence_manifest.json").read_text())
    if audit["frames"] != 301 or len(sequence) != 301 or not audit["diagnostic_only"]:
        raise SystemExit("SCOPE27_INPUT_BLOCKED")
    tracker_config = {
        "detector_confidence_floor": 0.10,
        "track_low_thresh": 0.10,
        "track_high_thresh": 0.25,
        "new_track_thresh": 0.35,
        "match_iou": 0.30,
        "adaptive_center_gate": 2.50,
        "adaptive_mahalanobis_gate": 25.0,
        "process_noise": 1.0,
        "measurement_noise": 4.0,
        "min_confirmed_observations": 2,
        "max_lost_seconds": 0.60,
        "max_gap_before_reset_seconds": 1.00,
    }
    config = {"candidate_id": audit["candidate_id"], "model_dir": f"{REMOTE}/model", "video": f"{REMOTE}/V_DRONE_001.mp4", "sequence_manifest": f"{REMOTE}/sequence_manifest.json", "output_dir": f"{REMOTE}/output", "sequence_id": audit["sequence_id"], "param_sha256": audit["detector"]["param_sha256"], "bin_sha256": audit["detector"]["bin_sha256"], "tracker_config": tracker_config}
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.1.118", username="pitan", password="1234", look_for_keys=False, allow_agent=False, timeout=10, auth_timeout=10, banner_timeout=10)
    try:
        _, out, err = client.exec_command(f"mkdir -p {REMOTE}/model {REMOTE}/src/anti_drone/tracking {REMOTE}/output")
        if out.channel.recv_exit_status() != 0:
            raise SystemExit(err.read().decode(errors="replace"))
        sftp = client.open_sftp()
        files = [
            (PACKAGE / "model.ncnn.param", f"{REMOTE}/model/model.ncnn.param"),
            (PACKAGE / "model.ncnn.bin", f"{REMOTE}/model/model.ncnn.bin"),
            (ROOT / "scripts/scope21_pi_runner.py", f"{REMOTE}/scope21_pi_runner.py"),
            (ROOT / "scripts/scope27_pi_dryrun.py", f"{REMOTE}/dryrun.py"),
            (ROOT / "data/tracking_eval/sequence_001/source/V_DRONE_001.mp4", f"{REMOTE}/V_DRONE_001.mp4"),
            (RUNTIME / "sequence_manifest.json", f"{REMOTE}/sequence_manifest.json"),
        ]
        for local, remote in files:
            sftp.put(str(local), remote)
        sftp.put(str(ROOT / "src/anti_drone/__init__.py"), f"{REMOTE}/src/anti_drone/__init__.py")
        for local in sorted((ROOT / "src/anti_drone/tracking").glob("*.py")):
            sftp.put(str(local), f"{REMOTE}/src/anti_drone/tracking/{local.name}")
        (RUNTIME / "dryrun_config.json").write_text(json.dumps(config, indent=2) + "\n")
        sftp.put(str(RUNTIME / "dryrun_config.json"), f"{REMOTE}/config.json")
        sftp.close()
        _, stdout, stderr = client.exec_command(f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python dryrun.py", timeout=900)
        output = stdout.read().decode(errors="replace")
        error = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        (RUNTIME / "dryrun_stdout.log").write_text(output)
        (RUNTIME / "dryrun_stderr.log").write_text(error)
        sftp = client.open_sftp()
        sftp.get(f"{REMOTE}/output/summary.json", str(RUNTIME / "dryrun_summary.json"))
        sftp.get(f"{REMOTE}/output/target_state.jsonl", str(RUNTIME / "target_state.jsonl"))
        sftp.close()
        result = json.loads((RUNTIME / "dryrun_summary.json").read_text())
        print(json.dumps({"ssh_exit": code, "status": result.get("status"), "frames": result.get("frames_processed"), "track_ids": result.get("track_ids_created"), "events": {key: value["count"] for key, value in result.get("events", {}).items()}, "effective_fps": result.get("effective_fps"), "actuator": result.get("actuator"), "stderr": error[-500:]}, indent=2))
        return 0 if code == 0 and result.get("status") == "DRY_RUN_COMPLETE" else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
