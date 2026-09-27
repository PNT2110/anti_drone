#!/usr/bin/env python3
"""Transfer and run Scope 28 only on the verified Raspberry Pi 5."""
from __future__ import annotations

import json
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope28"
PACKAGE = ROOT / "artifacts/production-candidate/scope25"
REMOTE = "/home/pitan/antidrone-scope28-dryrun"


def main() -> int:
    audit = json.loads((RUNTIME / "input_audit.json").read_text())
    if audit["scope28_status"] != "CONTRACT_GAP_CONFIDENCE_FLOOR" or audit["halmstad_frames"] != 301:
        raise SystemExit("SCOPE28_INPUT_BLOCKED")
    benchmark = json.loads((ROOT / ".runtime/scope19/benchmark_input_manifest.json").read_text())
    if benchmark.get("split") != "train" or benchmark.get("test_accessed") is not False or len(benchmark.get("paths", [])) != 8:
        raise SystemExit("SCOPE28_PARITY_INPUT_BLOCKED")
    tracker_config = audit["tracker_config"]
    config = {"candidate_id": audit["candidate_id"], "model_dir": f"{REMOTE}/model", "video": f"{REMOTE}/V_DRONE_001.mp4", "sequence_manifest": f"{REMOTE}/sequence_manifest.json", "output_dir": f"{REMOTE}/output", "input_root": f"{REMOTE}/inputs", "reference": f"{REMOTE}/host_reference.json", "run_id": "scope18-yolov8n-480", "images": [{"filename": Path(path).name} for path in benchmark["paths"]], "param_sha256": audit["detector"]["param_sha256"], "bin_sha256": audit["detector"]["bin_sha256"], "tracker_config": tracker_config}
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.1.118", username="pitan", password="1234", look_for_keys=False, allow_agent=False, timeout=10, auth_timeout=10, banner_timeout=10)
    try:
        _, out, err = client.exec_command(f"mkdir -p {REMOTE}/model {REMOTE}/inputs {REMOTE}/src/anti_drone/tracking {REMOTE}/output")
        if out.channel.recv_exit_status() != 0:
            raise SystemExit(err.read().decode(errors="replace"))
        sftp = client.open_sftp()
        files = [
            (PACKAGE / "model.ncnn.param", f"{REMOTE}/model/model.ncnn.param"),
            (PACKAGE / "model.ncnn.bin", f"{REMOTE}/model/model.ncnn.bin"),
            (ROOT / "scripts/scope21_pi_runner.py", f"{REMOTE}/scope21_pi_runner.py"),
            (ROOT / "scripts/scope28_pi_runner.py", f"{REMOTE}/scope28_pi_runner.py"),
            (ROOT / "data/tracking_eval/sequence_001/source/V_DRONE_001.mp4", f"{REMOTE}/V_DRONE_001.mp4"),
            (RUNTIME / "sequence_manifest.json" if (RUNTIME / "sequence_manifest.json").exists() else ROOT / ".runtime/scope27/sequence_manifest.json", f"{REMOTE}/sequence_manifest.json"),
            (ROOT / ".runtime/scope25/host_reference.json", f"{REMOTE}/host_reference.json"),
        ]
        for local, remote in files:
            sftp.put(str(local), remote)
        sftp.put(str(ROOT / "src/anti_drone/__init__.py"), f"{REMOTE}/src/anti_drone/__init__.py")
        sftp.put(str(ROOT / "src/anti_drone/scope28_contract.py"), f"{REMOTE}/src/anti_drone/scope28_contract.py")
        for local in sorted((ROOT / "src/anti_drone/tracking").glob("*.py")):
            sftp.put(str(local), f"{REMOTE}/src/anti_drone/tracking/{local.name}")
        for path in benchmark["paths"]:
            local = Path(path); sftp.put(str(local), f"{REMOTE}/inputs/{local.name}")
        (RUNTIME / "scope28_pi_config.json").write_text(json.dumps(config, indent=2) + "\n")
        sftp.put(str(RUNTIME / "scope28_pi_config.json"), f"{REMOTE}/config.json")
        sftp.close()
        client.exec_command(f"rm -f {REMOTE}/output/*")
        for mode, log_name in (("legacy_reference", "legacy_reference"), ("dual", "dual")):
            _, stdout, stderr = client.exec_command(f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope28_pi_runner.py --config config.json --mode {mode}", timeout=900)
            output = stdout.read().decode(errors="replace"); error = stderr.read().decode(errors="replace"); code = stdout.channel.recv_exit_status()
            (RUNTIME / f"{log_name}_stdout.log").write_text(output); (RUNTIME / f"{log_name}_stderr.log").write_text(error)
            if code != 0:
                print(json.dumps({"mode": mode, "ssh_exit": code, "stdout": output[-1000:], "stderr": error[-1000:]}, indent=2)); return 2
        sftp = client.open_sftp()
        for name in ("summary.json", "target_state.jsonl", "stream_records.jsonl", "public_reference.jsonl", "parity_8.json"):
            sftp.get(f"{REMOTE}/output/{name}", str(RUNTIME / name))
        sftp.close()
        result = json.loads((RUNTIME / "summary.json").read_text())
        print(json.dumps({"status": result.get("status"), "frames": result.get("frames_processed"), "parity_8": result.get("parity_8", {}).get("status"), "low_only": result.get("stream_aggregates", {}).get("low_only_frames"), "latency": result.get("latency_ms", {}).get("total_pipeline_ms"), "fps": result.get("effective_fps"), "hardware": result.get("hardware"), "stderr": ""}, indent=2))
        return 0 if result.get("status") == "DRY_RUN_COMPLETE" and result.get("parity_8", {}).get("status") == "PARITY_PASS" else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
