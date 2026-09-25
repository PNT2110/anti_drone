#!/usr/bin/env python3
"""Run the frozen 8-image NCNN parity smoke in a Scope 27 workspace."""
from __future__ import annotations

import json
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope27"
PACKAGE = ROOT / "artifacts/production-candidate/scope25"
REMOTE = "/home/pitan/antidrone-scope27-parity"


def main() -> int:
    benchmark = json.loads((ROOT / ".runtime/scope19/benchmark_input_manifest.json").read_text())
    if benchmark.get("split") != "train" or benchmark.get("test_accessed") is not False or len(benchmark.get("paths", [])) != 8:
        raise SystemExit("SCOPE27_PARITY_INPUT_BLOCKED")
    config = {"candidate_id": "scope18-yolov8n-480:ncnn", "run_id": "scope18-yolov8n-480", "model_dir": f"{REMOTE}/model", "artifact_hashes": {"model.ncnn.param": "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5", "model.ncnn.bin": "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"}, "images": [{"filename": Path(path).name} for path in benchmark["paths"]]}
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.1.118", username="pitan", password="1234", look_for_keys=False, allow_agent=False, timeout=10, auth_timeout=10, banner_timeout=10)
    try:
        _, out, err = client.exec_command(f"mkdir -p {REMOTE}/model {REMOTE}/inputs")
        if out.channel.recv_exit_status() != 0:
            raise SystemExit(err.read().decode(errors="replace"))
        sftp = client.open_sftp()
        for local, remote in ((PACKAGE / "model.ncnn.param", f"{REMOTE}/model/model.ncnn.param"), (PACKAGE / "model.ncnn.bin", f"{REMOTE}/model/model.ncnn.bin"), (ROOT / "scripts/scope21_pi_runner.py", f"{REMOTE}/scope21_pi_runner.py"), (ROOT / "scripts/scope27_parity_runner.py", f"{REMOTE}/parity_runner.py"), (ROOT / ".runtime/scope25/host_reference.json", f"{REMOTE}/host_reference.json")):
            sftp.put(str(local), remote)
        for path in benchmark["paths"]:
            local = Path(path)
            sftp.put(str(local), f"{REMOTE}/inputs/{local.name}")
        (RUNTIME / "parity_config.json").write_text(json.dumps(config, indent=2) + "\n")
        sftp.put(str(RUNTIME / "parity_config.json"), f"{REMOTE}/config.json")
        sftp.close()
        _, stdout, stderr = client.exec_command(f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python parity_runner.py", timeout=300)
        output = stdout.read().decode(errors="replace")
        error = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        (RUNTIME / "parity_smoke_stdout.log").write_text(output)
        (RUNTIME / "parity_smoke_stderr.log").write_text(error)
        sftp = client.open_sftp()
        sftp.get(f"{REMOTE}/parity_result.json", str(RUNTIME / "parity_smoke.json"))
        sftp.close()
        result = json.loads((RUNTIME / "parity_smoke.json").read_text())
        print(json.dumps({"ssh_exit": code, "status": result.get("status"), "images": len(result.get("images", [])), "stderr": error[-500:]}, indent=2))
        return 0 if code == 0 and result.get("status") == "PARITY_PASS" else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
