#!/usr/bin/env python3
"""Promote the prepared candidate only after real Pi 5 evidence exists."""

from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, default=Path("artifacts/releases/yolov8n"))
    parser.add_argument("--benchmark-root", type=Path, default=Path("artifacts/benchmarks/pi5-cpu"))
    parser.add_argument("--camera-report", type=Path, action="append", required=True, help="Camera report; repeat once per runtime")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--pi-machine", choices=("aarch64", "arm64"), help="Machine recorded by the remote Pi evidence")
    args = parser.parse_args()
    reasons: list[str] = []
    if args.pi_machine is None and platform.machine() not in {"aarch64", "arm64"}:
        reasons.append(f"machine={platform.machine()}, expected Raspberry Pi 5 aarch64")
    cameras = {}
    for camera_path in args.camera_report:
        camera = json.loads(camera_path.read_text())
        runtime = camera.get("runtime", camera_path.parent.name)
        cameras[runtime] = {"path": str(camera_path), **camera}
        if camera.get("status") != "DONE":
            reasons.append(f"{runtime} camera status is {camera.get('status')}")
        if float(camera.get("duration_seconds", 0)) < 1800:
            reasons.append(f"{runtime} camera sustained duration is below 1800 seconds")
    benchmarks = {}
    evidence_machines = set()
    for runtime in ("onnx", "ncnn", "tflite"):
        report = args.benchmark_root / runtime / args.run_id / "benchmark.json"
        if not report.exists():
            reasons.append(f"missing {report}")
            continue
        benchmark = json.loads(report.read_text())
        benchmarks[runtime] = benchmark
        environment_path = report.parent / "environment.json"
        if environment_path.exists():
            evidence_machines.add(json.loads(environment_path.read_text()).get("machine"))
        if benchmark.get("status") != "DONE_PI":
            reasons.append(f"{runtime} status is {benchmark.get('status')}")
        if benchmark.get("frames", 0) < 1000:
            reasons.append(f"{runtime} has fewer than 1000 measured frames")
    if args.pi_machine is not None:
        if evidence_machines != {args.pi_machine}:
            reasons.append(f"benchmark evidence machines={sorted(evidence_machines)}, expected {args.pi_machine}")
    if reasons:
        print(json.dumps({"status": "BLOCKED_PI_VALIDATION", "reasons": reasons}, indent=2))
        raise SystemExit(2)
    release_path = args.release_dir / "release.json"
    release = json.loads(release_path.read_text())
    release["status"] = "RELEASE_CANDIDATE"
    release["pi_validation"] = {"camera_reports": cameras, "run_id": args.run_id, "benchmarks": benchmarks, "promoted_at_unix": time.time(), "machine": args.pi_machine or platform.machine()}
    release_path.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    (args.release_dir / "RELEASE_CANDIDATE.md").write_text(
        "# Anti-drone release candidate — yolov8n\n\n"
        "Status: `RELEASE_CANDIDATE`\n\n"
        f"Pi camera and three runtime benchmarks passed for run `{args.run_id}`.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": release["status"], "run_id": args.run_id}, indent=2))


if __name__ == "__main__":
    main()
