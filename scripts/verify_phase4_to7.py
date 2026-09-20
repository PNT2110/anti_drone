#!/usr/bin/env python3
"""Independent completion audit for the Phase 4–7 artifacts."""

from __future__ import annotations

import hashlib
import json
import platform
import tarfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_file(path: Path, failures: list[str]) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        failures.append(f"missing_or_empty:{path.relative_to(ROOT)}")


def main() -> None:
    failures: list[str] = []
    deployment = ROOT / "artifacts/deploy/yolov8n"
    required_deployment = [
        deployment / "metadata.json", deployment / "parity.json", deployment / "SHA256SUMS",
        deployment / "onnx/best.onnx", deployment / "ncnn/best_ncnn_model/model.ncnn.param",
        deployment / "ncnn/best_ncnn_model/model.ncnn.bin", deployment / "tflite/model_float32.tflite",
    ]
    for path in required_deployment:
        check_file(path, failures)
    parity = json.loads((deployment / "parity.json").read_text()) if (deployment / "parity.json").exists() else {}
    if parity.get("status") != "DONE":
        failures.append(f"phase4_parity:{parity.get('status')}")
    for runtime, item in parity.get("profiles", {}).items():
        if item.get("status") != "DONE":
            failures.append(f"phase4_profile:{runtime}:{item.get('status')}")
    checksum_failures = []
    sums = deployment / "SHA256SUMS"
    if sums.exists():
        for line in sums.read_text().splitlines():
            if not line.strip():
                continue
            expected, relative = line.split("  ", 1)
            target = deployment / relative
            if not target.exists() or sha256(target) != expected:
                checksum_failures.append(relative)
    if checksum_failures:
        failures.append("deployment_checksum:" + ",".join(checksum_failures))
    bundle_path = ROOT / "artifacts/releases/yolov8n/anti-drone-yolov8n-pi5.tar.gz"
    bundle_manifest_path = ROOT / "artifacts/releases/yolov8n/PI5_BUNDLE_MANIFEST.json"
    bundle_failures: list[str] = []
    bundle_file_count = 0
    if bundle_path.exists() and bundle_manifest_path.exists():
        bundle_manifest = json.loads(bundle_manifest_path.read_text())
        if sha256(bundle_path) != bundle_manifest.get("bundle_sha256"):
            bundle_failures.append("bundle_sha256_mismatch")
        with tarfile.open(bundle_path, "r:gz") as archive:
            members = {member.name: member for member in archive.getmembers() if member.isfile()}
            for item in bundle_manifest.get("files", []):
                archive_name = f"anti-drone/{item['path']}"
                member = members.get(archive_name)
                if member is None:
                    bundle_failures.append(f"missing:{item['path']}")
                    continue
                payload = archive.extractfile(member).read()
                if hashlib.sha256(payload).hexdigest() != item["sha256"]:
                    bundle_failures.append(f"sha256:{item['path']}")
            bundle_file_count = len(members)
            if bundle_file_count != len(bundle_manifest.get("files", [])):
                bundle_failures.append(f"file_count:{bundle_file_count}!={len(bundle_manifest.get('files', []))}")
    else:
        bundle_failures.append("bundle_or_manifest_missing")
    if bundle_failures:
        failures.append("pi_bundle:" + ",".join(bundle_failures))

    replay = {}
    for runtime in ("onnx", "ncnn", "tflite"):
        path = ROOT / f".runtime/pi-replay/{runtime}/replay_report.json"
        check_file(path, failures)
        if path.exists():
            replay[runtime] = json.loads(path.read_text())
            if replay[runtime].get("status") != "DONE":
                failures.append(f"phase5_replay:{runtime}:{replay[runtime].get('status')}")
    camera_path = ROOT / ".runtime/pi-camera-test/onnx/camera_report.json"
    check_file(camera_path, failures)
    camera = json.loads(camera_path.read_text()) if camera_path.exists() else {}
    if camera.get("status") != "BLOCKED":
        failures.append(f"camera_probe_unexpected:{camera.get('status')}")

    benchmarks = {}
    for runtime in ("onnx", "ncnn", "tflite"):
        path = ROOT / f"artifacts/benchmarks/pi5-cpu/{runtime}/20260920-hostref/benchmark.json"
        check_file(path, failures)
        if path.exists():
            benchmarks[runtime] = json.loads(path.read_text())
            if benchmarks[runtime].get("status") != "DONE_HOST_REFERENCE":
                failures.append(f"phase6_host_benchmark:{runtime}:{benchmarks[runtime].get('status')}")
            if benchmarks[runtime].get("frames") != 1000:
                failures.append(f"phase6_frame_count:{runtime}:{benchmarks[runtime].get('frames')}")

    pi_benchmarks = {}
    pi_camera = {}
    pi_run_id = None
    pi_root = ROOT / "artifacts/benchmarks/pi5-cpu"
    candidate_run_ids = set()
    for runtime in ("onnx", "ncnn", "tflite"):
        runtime_root = pi_root / runtime
        if runtime_root.exists():
            candidate_run_ids.update(path.name for path in runtime_root.iterdir() if path.is_dir() and path.name != "20260920-hostref")
    for run_id in sorted(candidate_run_ids, reverse=True):
        if all((pi_root / runtime / run_id / "benchmark.json").exists() for runtime in ("onnx", "ncnn", "tflite")):
            pi_run_id = run_id
            break
    if pi_run_id:
        for runtime in ("onnx", "ncnn", "tflite"):
            path = pi_root / runtime / pi_run_id / "benchmark.json"
            pi_benchmarks[runtime] = json.loads(path.read_text())
            if pi_benchmarks[runtime].get("status") != "DONE_PI":
                failures.append(f"phase6_pi_benchmark:{runtime}:{pi_benchmarks[runtime].get('status')}")
            if pi_benchmarks[runtime].get("frames", 0) < 1000:
                failures.append(f"phase6_pi_frame_count:{runtime}:{pi_benchmarks[runtime].get('frames')}")
            environment = path.parent / "environment.json"
            if not environment.exists() or json.loads(environment.read_text()).get("machine") not in {"aarch64", "arm64"}:
                failures.append(f"phase6_pi_machine:{runtime}")
        for runtime in ("onnx", "ncnn", "tflite"):
            path = ROOT / f".runtime/pi-camera/{runtime}/camera_report.json"
            if path.exists():
                pi_camera[runtime] = json.loads(path.read_text())
                if pi_camera[runtime].get("status") != "DONE" or float(pi_camera[runtime].get("duration_seconds", 0)) < 1800:
                    failures.append(f"phase5_pi_camera:{runtime}")
            else:
                failures.append(f"phase5_pi_camera_missing:{runtime}")

    manifest = ROOT / "data/processed/drone-single-class/manifest.json"
    phase3_provenance = ROOT / "artifacts/benchmarks/model-selection/yolov8n/provenance.json"
    check_file(manifest, failures)
    check_file(phase3_provenance, failures)
    manifest_hash = sha256(manifest) if manifest.exists() else None
    expected_hash = json.loads(phase3_provenance.read_text()).get("dataset_manifest_sha256") if phase3_provenance.exists() else None
    if manifest_hash != expected_hash:
        failures.append(f"dataset_v1_hash_changed:{manifest_hash}!={expected_hash}")
    incoming = ROOT / "data/incoming"
    incoming_files = [path for path in incoming.rglob("*") if path.is_file() and path.name != ".gitkeep"] if incoming.exists() else []
    pi_ready = bool(pi_run_id) and len(pi_benchmarks) == 3 and len(pi_camera) == 3 and all(item.get("status") == "DONE" for item in pi_camera.values())
    status = "COMPLETE" if pi_ready and not failures else ("BLOCKED_PI_VALIDATION" if platform.machine() not in {"aarch64", "arm64"} or camera.get("status") != "DONE" else "REVIEW_REQUIRED")
    report = {
        "status": status,
        "failures": failures,
        "phase4": {"parity": parity.get("status"), "deployment_checksum_failures": checksum_failures},
        "pi_bundle": {"status": "DONE" if not bundle_failures else "BLOCKED", "file_count": bundle_file_count, "failures": bundle_failures},
        "phase5": {"replay": {key: value.get("status") for key, value in replay.items()}, "camera": camera.get("status")},
        "phase6": {"benchmarks": {key: value.get("status") for key, value in benchmarks.items()}, "pi_run_id": pi_run_id, "pi_benchmarks": {key: value.get("status") for key, value in pi_benchmarks.items()}, "hardware": platform.machine()},
        "phase5_pi": {"camera": {key: value.get("status") for key, value in pi_camera.items()}},
        "phase7": {"dataset_manifest_sha256": manifest_hash, "matches_phase3": manifest_hash == expected_hash, "incoming_reviewed_files": [str(path.relative_to(ROOT)) for path in incoming_files]},
        "timestamp_unix": time.time(),
    }
    output = ROOT / "artifacts/releases/yolov8n/VERIFICATION.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output.parent / "VERIFICATION.md").write_text(
        "# Phase 4–7 independent verification\n\n"
        f"Status: `{status}`\n\n"
        f"Failures: `{len(failures)}`\n\n"
        "Phase 4 artifacts, replay outputs, benchmarks and dataset immutability were checked. "
        f"Pi evidence run: `{pi_run_id}`.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if not failures else 2)


if __name__ == "__main__":
    main()
