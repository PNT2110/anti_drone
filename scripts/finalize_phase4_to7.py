#!/usr/bin/env python3
"""Create the auditable Phase 4–7 handoff and release status."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    else:
        for item in sorted(path.rglob("*")):
            if item.is_file():
                digest.update(str(item.relative_to(path)).encode())
                with item.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    deploy = root / "artifacts/deploy/yolov8n"
    parity = json.loads((deploy / "parity.json").read_text())
    metadata = json.loads((deploy / "metadata.json").read_text())
    replay = {}
    for runtime in ("onnx", "ncnn", "tflite"):
        replay[runtime] = json.loads((root / f".runtime/pi-replay/{runtime}/replay_report.json").read_text())
    benchmarks = {}
    for runtime in ("onnx", "ncnn", "tflite"):
        benchmarks[runtime] = json.loads((root / f"artifacts/benchmarks/pi5-cpu/{runtime}/20260920-hostref/benchmark.json").read_text())
    camera = json.loads((root / ".runtime/pi-camera-test/onnx/camera_report.json").read_text())
    incoming = root / "data/incoming"
    incoming_entries = sorted(
        str(path.relative_to(root))
        for path in incoming.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    ) if incoming.exists() else []
    dataset_manifest = root / "data/processed/drone-single-class/manifest.json"
    maintenance = {
        "status": "BASELINE_FROZEN_NO_NEW_BATCH",
        "dataset": str(dataset_manifest),
        "dataset_manifest_sha256": sha256(dataset_manifest),
        "release_model": "yolov8n",
        "release_checkpoint_sha256": metadata["checkpoint_sha256"],
        "incoming_batch_files": incoming_entries,
        "rule": "Dataset v1 remains unchanged; no v2 retrain is authorized without a reviewed incoming batch.",
        "timestamp_unix": time.time(),
    }
    maintenance_dir = root / "artifacts/maintenance/yolov8n"
    maintenance_dir.mkdir(parents=True, exist_ok=True)
    (maintenance_dir / "phase7_status.json").write_text(json.dumps(maintenance, indent=2) + "\n", encoding="utf-8")
    (maintenance_dir / "PHASE_07_STATUS.md").write_text(f"""# Phase 07 maintenance status

Status: `{maintenance['status']}`

Dataset v1 is frozen and its manifest hash is `{maintenance['dataset_manifest_sha256']}`.
No incoming reviewed batch exists, so no pseudo-retrain or fabricated v2 dataset
was created. The next batch must follow the Phase 07 runbook and pass Phase 03
before export or release replacement.
""", encoding="utf-8")

    release = {
        "status": "BLOCKED_PI_VALIDATION",
        "model_id": "yolov8n",
        "phase4": {"status": metadata["status"], "parity_status": parity["status"], "deployment": str(deploy)},
        "phase5": {
            "replay": {key: value["status"] for key, value in replay.items()},
            "camera": camera["status"],
            "camera_reason": "No /dev/video0 was present on the current x86_64 host.",
        },
        "phase6": {
            "benchmarks": {key: value["status"] for key, value in benchmarks.items()},
            "pi_acceptance": "BLOCKED: all measurements are host references, not Raspberry Pi 5 measurements.",
        },
        "phase7": maintenance,
        "pi_handoff_bundle": {
            "path": str(root / "artifacts/releases/yolov8n/anti-drone-yolov8n-pi5.tar.gz"),
            "manifest": str(root / "artifacts/releases/yolov8n/PI5_BUNDLE_MANIFEST.json"),
            "status": "HOST_VERIFIED_PI_HANDOFF",
        },
        "host_reference": {
            runtime: {
                "model_only_fps": value["model_only_fps_mean"],
                "end_to_end_fps": value["end_to_end_fps_mean"],
                "frames": value["frames"],
            }
            for runtime, value in benchmarks.items()
        },
        "platform": {"machine": platform.machine(), "system": platform.platform()},
        "timestamp_unix": time.time(),
    }
    release_dir = root / "artifacts/releases/yolov8n"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "release.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    (release_dir / "RELEASE_CANDIDATE.md").write_text(f"""# Anti-drone release candidate — yolov8n

Status: `BLOCKED_PI_VALIDATION`

## Completed

- Phase 04 export and parity: `{metadata['status']}`.
- Phase 05 image replay: all three profiles completed.
- Phase 06 host reference: 1,000 measured frames per runtime after 200 warm-up frames.
- Phase 07: dataset v1 frozen; no unreviewed data was introduced.

## Blocking gate

The current machine is `{platform.machine()}` and has no `/dev/video0`. It cannot
prove Raspberry Pi 5 4GB camera stability, thermal behavior, 30-minute sustained
operation, or Pi-specific latency. Do not publish the host FPS values as Pi FPS.

The prepared handoff bundle is `anti-drone-yolov8n-pi5.tar.gz`; its manifest and
SHA256 are stored beside this report. It still requires the Pi validation gate.

Run the Phase 05 camera test and Phase 06 benchmark commands on the actual Pi,
then replace this status only when all three runtime reports contain Pi hardware
metadata and the sustained run completes without a crash.
""", encoding="utf-8")
    print(json.dumps({"release": str(release_dir), "status": release["status"], "phase4": parity["status"], "phase5_camera": camera["status"]}, indent=2))


if __name__ == "__main__":
    main()
