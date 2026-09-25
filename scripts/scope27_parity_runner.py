#!/usr/bin/env python3
"""Scope 27 detector-only parity smoke on the Pi, separate from Scope 25."""
from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path

import cv2
import numpy as np

from scope21_pi_runner import compare, infer, load_runtime, meminfo, vcgencmd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    config = json.loads(Path("config.json").read_text())
    model_dir = Path(config["model_dir"])
    hardware = {"uname": platform.uname()._asdict(), "machine": platform.machine(), "model": Path("/proc/device-tree/model").read_text(errors="replace").strip("\x00\n") if Path("/proc/device-tree/model").exists() else None, "memory_before": meminfo(), "temperature_before": vcgencmd("measure_temp"), "throttling_before": vcgencmd("get_throttled")}
    result = {"status": "PARITY_PASS", "candidate_id": config["candidate_id"], "backend": "NCNN", "precision": "FP32", "imgsz": 480, "confidence": 0.25, "nms_iou": 0.70, "warmup_passes": 5, "measured_passes": 10, "hardware": hardware, "artifact_hashes": {}, "images": [], "test_accessed": False}
    if hardware["machine"] != "aarch64" or "Raspberry Pi 5 Model B Rev 1.0" not in (hardware["model"] or ""):
        result["status"] = "PI_IDENTITY_FAIL"
    for name, expected in config["artifact_hashes"].items():
        actual = sha256(model_dir / name)
        result["artifact_hashes"][name] = {"expected": expected, "actual": actual, "match": actual == expected}
        if actual != expected:
            result["status"] = "PARITY_FAIL"
    if result["status"] == "PARITY_PASS":
        runtime, runtime_meta = load_runtime({"backend": "ncnn", "artifact_path": str(model_dir), "threads": 4})
        result["runtime"] = runtime_meta
        reference = {(row["run_id"], row["image"]): row for row in json.loads(Path("host_reference.json").read_text())["records"]}
        for item in config["images"]:
            image = cv2.imread(str(Path("inputs") / item["filename"]))
            if image is None:
                result["status"] = "PARITY_FAIL"
                result.setdefault("errors", []).append(item["filename"])
                continue
            for _ in range(result["warmup_passes"]):
                infer(runtime, {"backend": "ncnn", "threads": 4}, image, 480)
            times = []
            detections = None
            contract = None
            for _ in range(result["measured_passes"]):
                started = time.perf_counter()
                detections, contract, _ = infer(runtime, {"backend": "ncnn", "threads": 4}, image, 480)
                times.append((time.perf_counter() - started) * 1000.0)
            comparison = compare(reference[(config["run_id"], item["filename"])]["detections"], detections)
            result["images"].append({"image": item["filename"], "contract": contract, "parity": comparison, "latency_ms": {"mean": float(np.mean(times)), "p50": float(np.percentile(times, 50)), "p95": float(np.percentile(times, 95))}})
            if comparison["status"] != "PARITY_PASS":
                result["status"] = "PARITY_FAIL"
    hardware["memory_after"] = meminfo()
    hardware["temperature_after"] = vcgencmd("measure_temp")
    hardware["throttling_after"] = vcgencmd("get_throttled")
    result["hardware"] = hardware
    Path("parity_result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "images": len(result["images"]), "parity": [row["parity"]["status"] for row in result["images"]], "runtime": result.get("runtime")}, indent=2), flush=True)
    return 0 if result["status"] == "PARITY_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
