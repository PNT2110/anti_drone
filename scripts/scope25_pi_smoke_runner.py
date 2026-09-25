#!/usr/bin/env python3
"""Short fixed-input Scope 25 smoke runner executed on the Pi."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

from scope21_pi_runner import compare, infer, load_runtime, rss_kb, meminfo, vcgencmd


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    cfg = json.loads(Path("config.json").read_text())
    model_dir = Path(cfg["model_dir"])
    hardware = {
        "uname": platform.uname()._asdict(),
        "machine": platform.machine(),
        "model": Path("/proc/device-tree/model").read_text(errors="replace").strip("\x00\n") if Path("/proc/device-tree/model").exists() else None,
        "memory_before": meminfo(),
        "temperature_before": vcgencmd("measure_temp"),
        "throttling_before": vcgencmd("get_throttled"),
    }
    warmup_passes = 20
    measured_passes = 20
    result = {"status": "SMOKE_PASS", "candidate_id": cfg["candidate_id"], "run_id": cfg["run_id"], "size": cfg["size"], "backend": "ncnn", "precision": "FP32", "threads": 4, "hardware": hardware, "artifact_hashes": {}, "images": [], "warmup_passes": warmup_passes, "measured_passes": measured_passes, "test_accessed": False}
    if hardware["machine"] != "aarch64" or "Raspberry Pi 5 Model B Rev 1.0" not in (hardware["model"] or ""):
        result["status"] = "FREEZE_REPRODUCTION_FAIL"
        result["reason"] = "Pi identity mismatch"
    else:
        for name, expected in cfg["artifact_hashes"].items():
            actual = sha256(model_dir / name)
            result["artifact_hashes"][name] = {"expected": expected, "actual": actual, "match": actual == expected}
            if actual != expected:
                result["status"] = "FREEZE_REPRODUCTION_FAIL"
        try:
            runtime, runtime_meta = load_runtime({"backend": "ncnn", "artifact_path": str(model_dir), "threads": 4})
            result["runtime"] = runtime_meta
            ref = {(x["run_id"], x["image"]): x for x in json.loads(Path("host_reference.json").read_text())["records"]}
            for item in cfg["images"]:
                image = cv2.imread(str(Path("inputs") / item["filename"]))
                if image is None:
                    raise FileNotFoundError(item["filename"])
                for _ in range(warmup_passes):
                    infer(runtime, {"backend": "ncnn", "threads": 4}, image, cfg["size"])
                times = []
                detections = None
                contract = None
                for _ in range(measured_passes):
                    t0 = time.perf_counter()
                    detections, contract, _ = infer(runtime, {"backend": "ncnn", "threads": 4}, image, cfg["size"])
                    times.append((time.perf_counter() - t0) * 1000.0)
                parity = compare(ref[(cfg["run_id"], item["filename"])]["detections"], detections)
                result["images"].append({"image": item["filename"], "contract": contract, "parity": parity, "latency_ms": {"mean": float(np.mean(times)), "p50": float(np.percentile(times, 50)), "p95": float(np.percentile(times, 95)), "fps": float(1000.0 / np.mean(times))}})
                if parity["status"] != "PARITY_PASS":
                    result["status"] = "FREEZE_REPRODUCTION_FAIL"
        except Exception as exc:
            result["status"] = "FREEZE_REPRODUCTION_FAIL"
            result["error"] = repr(exc)
    hardware["memory_after"] = meminfo()
    hardware["temperature_after"] = vcgencmd("measure_temp")
    hardware["throttling_after"] = vcgencmd("get_throttled")
    result["hardware"] = hardware
    Path("smoke_result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "image_count": len(result["images"]), "runtime": result.get("runtime"), "hardware": {k: hardware.get(k) for k in ("model", "machine", "temperature_before", "temperature_after", "throttling_before", "throttling_after")}}, indent=2))
    return 0 if result["status"] == "SMOKE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
