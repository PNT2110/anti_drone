#!/usr/bin/env python3
"""Run the frozen NCNN candidate over the locked Scope 26 TEST manifest on Pi."""
from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path

import cv2

from scope21_pi_runner import infer, load_runtime, meminfo, vcgencmd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    config = json.loads(Path("config.json").read_text())
    model_dir = Path(config["model_dir"])
    hardware = {
        "uname": platform.uname()._asdict(),
        "machine": platform.machine(),
        "model": Path("/proc/device-tree/model").read_text(errors="replace").strip("\x00\n") if Path("/proc/device-tree/model").exists() else None,
        "memory_before": meminfo(),
        "temperature_before": vcgencmd("measure_temp"),
        "throttling_before": vcgencmd("get_throttled"),
    }
    result = {
        "status": "FINAL_TEST_COMPLETE",
        "candidate_id": config["candidate_id"],
        "backend": "NCNN",
        "precision": "FP32",
        "imgsz": 480,
        "threshold": 0.25,
        "nms_iou": 0.70,
        "runtime": None,
        "hardware": hardware,
        "artifact_hashes": {},
        "processed": 0,
        "skipped": 0,
        "skipped_records": [],
        "test_accessed": True,
    }
    if hardware["machine"] != "aarch64" or "Raspberry Pi 5 Model B Rev 1.0" not in (hardware["model"] or ""):
        result["status"] = "EVALUATION_BLOCKED"
        result["reason"] = "Pi identity mismatch"
        Path(config["result"]).write_text(json.dumps(result, indent=2) + "\n")
        return 2
    for name, expected in config["artifact_hashes"].items():
        actual = sha256(model_dir / name)
        result["artifact_hashes"][name] = {"expected": expected, "actual": actual, "match": actual == expected}
        if actual != expected:
            result["status"] = "EVALUATION_BLOCKED"
            result["reason"] = "artifact hash mismatch"
    if result["status"] != "FINAL_TEST_COMPLETE":
        Path(config["result"]).write_text(json.dumps(result, indent=2) + "\n")
        return 2

    runtime, runtime_meta = load_runtime({"backend": "ncnn", "artifact_path": str(model_dir), "threads": 4})
    result["runtime"] = runtime_meta
    manifest_path = Path(config["manifest"])
    output_path = Path(config["predictions"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total = sum(1 for _ in manifest_path.open())
    with manifest_path.open() as manifest, output_path.open("w") as output:
        for index, line in enumerate(manifest, 1):
            record = json.loads(line)
            image = cv2.imread(str(Path(config["input_root"]) / Path(record["image_rel"]).name))
            if image is None:
                result["skipped"] += 1
                result["skipped_records"].append({"sample_id": record["sample_id"], "reason": "image_decode_failed"})
                continue
            started = time.perf_counter()
            detections, contract, timing = infer(runtime, {"backend": "ncnn", "threads": 4}, image, 480)
            end_to_end_ms = (time.perf_counter() - started) * 1000.0
            output.write(json.dumps({
                "sample_id": record["sample_id"],
                "image_rel": record["image_rel"],
                "modality": record["modality"],
                "source_sequence": record["source_sequence"],
                "source_frame_index": record["source_frame_index"],
                "gt_boxes": record["gt_boxes"],
                "predictions": detections,
                "pred_object_count": len(detections),
                "contract": contract,
                "timing": timing | {"end_to_end_ms": end_to_end_ms},
            }, separators=(",", ":")) + "\n")
            result["processed"] += 1
            if index % 250 == 0:
                output.flush()
                print(json.dumps({"progress": index, "total": total, "processed": result["processed"], "skipped": result["skipped"]}), flush=True)
    hardware["memory_after"] = meminfo()
    hardware["temperature_after"] = vcgencmd("measure_temp")
    hardware["throttling_after"] = vcgencmd("get_throttled")
    result["hardware"] = hardware
    if result["processed"] != total or result["skipped"] != 0:
        result["status"] = "FINAL_TEST_INCOMPLETE"
    Path(config["result"]).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "processed": result["processed"], "skipped": result["skipped"], "runtime": result["runtime"], "hardware": {k: hardware.get(k) for k in ("model", "temperature_before", "temperature_after", "throttling_before", "throttling_after")}}, indent=2), flush=True)
    return 0 if result["status"] == "FINAL_TEST_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
