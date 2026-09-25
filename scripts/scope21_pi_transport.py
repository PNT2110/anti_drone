#!/usr/bin/env python3
"""Transfer and run the Scope 21 fixed-input benchmark over SSH.

The password is requested with getpass and is never written to a file,
argument list, configuration, or report.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/home/pitan/antidrone-scope21"


def mkdir_p(sftp: paramiko.SFTPClient, path: str) -> None:
    parts = Path(path).parts
    current = parts[0]
    for part in parts[1:]:
        current = str(Path(current) / part)
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def connect(host: str, user: str, password: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, look_for_keys=False, allow_agent=False, timeout=10)
    return client


def put(sftp: paramiko.SFTPClient, local: Path, remote: str, transferred: list[dict]) -> None:
    mkdir_p(sftp, str(Path(remote).parent))
    sftp.put(str(local), remote)
    transferred.append({"local": str(local), "remote": remote, "bytes": local.stat().st_size})


def prepare(host: str, user: str, password: str) -> None:
    audit = json.loads((ROOT / ".runtime/scope21/input_audit.json").read_text())
    benchmark = json.loads((ROOT / ".runtime/scope19/benchmark_input_manifest.json").read_text())
    reference_path = ROOT / ".runtime/scope21/host_reference.json"
    candidates = []
    uploads = []
    for row in audit["candidates"]:
        candidate_id = row["candidate_id"]
        local_artifact = Path(row["artifact"]["path"])
        remote_dir = f"{REMOTE_ROOT}/models/{candidate_id}"
        if row["backend"] == "onnx":
            remote_path = f"{remote_dir}/model.onnx"
            uploads.append((local_artifact, remote_path))
            artifact_hashes = {"": row["artifact"]["sha256"]}
            model_bytes = local_artifact.stat().st_size
            kind = "file"
        else:
            remote_path = f"{remote_dir}/model_ncnn_model"
            artifact_hashes = {}
            model_bytes = 0
            for item in row["artifact"]["files"]:
                local_file = local_artifact / item["relative"]
                remote_file = f"{remote_path}/{item['relative']}"
                uploads.append((local_file, remote_file))
                artifact_hashes[item["relative"]] = item["sha256"]
                model_bytes += item["bytes"]
            kind = "directory"
        candidates.append({**{k: row[k] for k in ("candidate_id", "run_id", "size", "backend")}, "artifact_path": remote_path, "artifact_kind": kind, "artifact_hashes": artifact_hashes, "model_bytes": model_bytes, "threads": 4})
    images = []
    for image_path in benchmark["paths"]:
        local = Path(image_path)
        remote = f"{REMOTE_ROOT}/inputs/{local.name}"
        uploads.append((local, remote))
        images.append({"filename": local.name})
    uploads.extend([(reference_path, f"{REMOTE_ROOT}/host_reference.json"), (ROOT / "scripts/scope21_pi_runner.py", f"{REMOTE_ROOT}/runner.py")])
    config = {"reference": f"{REMOTE_ROOT}/host_reference.json", "input_root": f"{REMOTE_ROOT}/inputs", "images": images, "candidates": candidates}
    config_path = ROOT / ".runtime/scope21/pi_config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    uploads.append((config_path, f"{REMOTE_ROOT}/config.json"))

    client = connect(host, user, password)
    try:
        sftp = client.open_sftp()
        mkdir_p(sftp, REMOTE_ROOT)
        transferred = []
        for local, remote in uploads:
            put(sftp, local, remote, transferred)
        (ROOT / ".runtime/scope21/transfer_manifest.json").write_text(json.dumps({"status": "TRANSFERRED", "remote_root": REMOTE_ROOT, "candidate_count": len(candidates), "file_count": len(transferred), "files": transferred}, indent=2) + "\n")
        command = f"cd {REMOTE_ROOT} && {REMOTE_ROOT}/venv/bin/python runner.py --config {REMOTE_ROOT}/config.json --output {REMOTE_ROOT}/results"
        _, stdout, stderr = client.exec_command(command)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        (ROOT / ".runtime/scope21/pi_runner_stdout.log").write_text(out)
        (ROOT / ".runtime/scope21/pi_runner_stderr.log").write_text(err)
        if exit_code not in (0, 2):
            raise RuntimeError(f"Pi runner exited {exit_code}: {err[-1000:]}")
        local_result = ROOT / ".runtime/scope21/pi_results"
        local_result.mkdir(parents=True, exist_ok=True)
        sftp.get(f"{REMOTE_ROOT}/results/benchmark_results.json", str(local_result / "benchmark_results.json"))
        print(json.dumps({"status": "COMPLETE", "runner_exit": exit_code, "result": str(local_result / "benchmark_results.json"), "stderr_tail": err[-500:]}))
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.1.118")
    parser.add_argument("--user", default="pitan")
    args = parser.parse_args()
    password = getpass.getpass("Pi SSH password: ")
    prepare(args.host, args.user, password)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
