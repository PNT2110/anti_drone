#!/usr/bin/env python3
"""Transfer only the verified Scope 25 smoke inputs to a separate Pi folder."""
from __future__ import annotations

import json
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "/home/pitan/antidrone-scope25-smoke"
NCNN = ROOT / "artifacts/exports/scope19/scope18-yolov8n-480/float32/ncnn/model_ncnn_model"


def mkdir_p(sftp, path: str):
    parts = Path(path).parts
    current = parts[0]
    for part in parts[1:]:
        current = str(Path(current) / part)
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def put(sftp, local: Path, remote: str):
    mkdir_p(sftp, str(Path(remote).parent))
    sftp.put(str(local), remote)


def run_smoke(host: str, user: str, password: str):
    audit = json.loads((ROOT / ".runtime/scope25/input_audit.json").read_text())
    benchmark = json.loads((ROOT / ".runtime/scope19/benchmark_input_manifest.json").read_text())
    reference = ROOT / ".runtime/scope25/host_reference.json"
    config = {
        "candidate_id": "scope18-yolov8n-480:ncnn",
        "run_id": "scope18-yolov8n-480",
        "size": 480,
        "model_dir": f"{REMOTE}/model",
        "artifact_hashes": {"model.ncnn.param": audit["ncnn"]["param_sha256"], "model.ncnn.bin": audit["ncnn"]["bin_sha256"]},
        "images": [{"filename": Path(p).name} for p in benchmark["paths"]],
    }
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, look_for_keys=False, allow_agent=False, timeout=10, auth_timeout=10, banner_timeout=10)
    try:
        sftp = client.open_sftp()
        mkdir_p(sftp, REMOTE)
        for local, remote in [(NCNN / "model.ncnn.param", f"{REMOTE}/model/model.ncnn.param"), (NCNN / "model.ncnn.bin", f"{REMOTE}/model/model.ncnn.bin"), (ROOT / "scripts/scope21_pi_runner.py", f"{REMOTE}/scope21_pi_runner.py"), (ROOT / "scripts/scope25_pi_smoke_runner.py", f"{REMOTE}/smoke_runner.py"), (reference, f"{REMOTE}/host_reference.json")]:
            put(sftp, local, remote)
        for p in benchmark["paths"]:
            local = Path(p)
            put(sftp, local, f"{REMOTE}/inputs/{local.name}")
        config["remote_root"] = REMOTE
        local_config = ROOT / ".runtime/scope25/pi_smoke_config.json"
        local_config.write_text(json.dumps(config, indent=2) + "\n")
        put(sftp, local_config, f"{REMOTE}/config.json")
        cmd = f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python smoke_runner.py"
        _, stdout, stderr = client.exec_command(cmd, timeout=180)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        (ROOT / ".runtime/scope25/pi_smoke_stdout.log").write_text(out)
        (ROOT / ".runtime/scope25/pi_smoke_stderr.log").write_text(err)
        sftp.get(f"{REMOTE}/smoke_result.json", str(ROOT / ".runtime/scope25/pi_smoke_result.json"))
        result = json.loads((ROOT / ".runtime/scope25/pi_smoke_result.json").read_text())
        print(json.dumps({"ssh_exit": code, "status": result.get("status"), "image_count": len(result.get("images", [])), "stderr_tail": err[-500:]}, indent=2))
        return 0 if code == 0 and result.get("status") == "SMOKE_PASS" else 2
    finally:
        client.close()
