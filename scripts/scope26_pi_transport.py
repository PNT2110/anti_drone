#!/usr/bin/env python3
"""Transfer the locked Scope 26 TEST subset and run production NCNN on Pi."""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope26"
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
REMOTE = "/home/pitan/antidrone-scope26"
PACKAGE = ROOT / "artifacts/production-candidate/scope25"


def put(sftp, local: Path, remote: str) -> None:
    sftp.put(str(local), remote)


def main() -> int:
    manifest = [json.loads(line) for line in (RUNTIME / "test_manifest.jsonl").read_text().splitlines()]
    if len(manifest) != 9848:
        raise SystemExit(f"TEST_MANIFEST_COUNT_MISMATCH: {len(manifest)}")
    names = [Path(row["image_rel"]).name for row in manifest]
    if len(set(names)) != len(names):
        raise SystemExit("TEST_IMAGE_NAME_COLLISION")
    config = {
        "candidate_id": "scope18-yolov8n-480:ncnn",
        "model_dir": f"{REMOTE}/model",
        "input_root": f"{REMOTE}/inputs",
        "manifest": f"{REMOTE}/test_manifest.jsonl",
        "predictions": f"{REMOTE}/predictions.jsonl",
        "result": f"{REMOTE}/runner_result.json",
        "artifact_hashes": {
            "model.ncnn.param": "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5",
            "model.ncnn.bin": "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7",
        },
    }
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.1.118", username="pitan", password="1234", look_for_keys=False, allow_agent=False, timeout=10, auth_timeout=10, banner_timeout=10)
    try:
        _, out, err = client.exec_command(f"mkdir -p {REMOTE}/model {REMOTE}/inputs")
        if out.channel.recv_exit_status() != 0:
            raise SystemExit(err.read().decode(errors="replace"))
        sftp = client.open_sftp()
        put(sftp, PACKAGE / "model.ncnn.param", f"{REMOTE}/model/model.ncnn.param")
        put(sftp, PACKAGE / "model.ncnn.bin", f"{REMOTE}/model/model.ncnn.bin")
        put(sftp, ROOT / "scripts/scope21_pi_runner.py", f"{REMOTE}/scope21_pi_runner.py")
        put(sftp, ROOT / "scripts/scope26_pi_runner.py", f"{REMOTE}/scope26_pi_runner.py")
        put(sftp, RUNTIME / "test_manifest.jsonl", f"{REMOTE}/test_manifest.jsonl")
        put(sftp, RUNTIME / "test_open_event.json", f"{REMOTE}/test_open_event.json")
        (RUNTIME / "pi_config.json").write_text(json.dumps(config, indent=2) + "\n")
        put(sftp, RUNTIME / "pi_config.json", f"{REMOTE}/config.json")
        sftp.close()

        _, tar_out, tar_err = client.exec_command(f"tar -xf - -C {REMOTE}/inputs", timeout=1800)
        tar_stream = tar_out.channel.makefile_stdin("wb")
        with tarfile.open(fileobj=tar_stream, mode="w|", format=tarfile.PAX_FORMAT) as archive:
            for index, row in enumerate(manifest, 1):
                source = DATASET / row["image_rel"]
                archive.add(str(source), arcname=Path(row["image_rel"]).name, recursive=False)
                if index % 1000 == 0:
                    print(json.dumps({"transfer_progress": index, "total": len(manifest)}), flush=True)
        tar_stream.close()
        tar_code = tar_out.channel.recv_exit_status()
        tar_error = tar_err.read().decode(errors="replace")
        if tar_code != 0:
            raise SystemExit(f"TEST_TRANSFER_FAILED: {tar_error}")

        command = f"cd {REMOTE} && /home/pitan/antidrone-scope21/venv/bin/python scope26_pi_runner.py"
        _, stdout, stderr = client.exec_command(command, timeout=3600)
        for line in iter(stdout.readline, ""):
            if line:
                print(line, end="", flush=True)
        code = stdout.channel.recv_exit_status()
        error = stderr.read().decode(errors="replace")
        (RUNTIME / "pi_runner_stderr.log").write_text(error)
        if code != 0:
            raise SystemExit(f"PI_TEST_RUN_FAILED exit={code}: {error[-2000:]}")
        sftp = client.open_sftp()
        sftp.get(f"{REMOTE}/runner_result.json", str(RUNTIME / "pi_runner_result.json"))
        sftp.get(f"{REMOTE}/predictions.jsonl", str(RUNTIME / "predictions.jsonl"))
        sftp.close()
        result = json.loads((RUNTIME / "pi_runner_result.json").read_text())
        print(json.dumps({"status": result.get("status"), "processed": result.get("processed"), "skipped": result.get("skipped"), "runtime": result.get("runtime")}, indent=2))
        return 0 if result.get("status") == "FINAL_TEST_COMPLETE" else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
