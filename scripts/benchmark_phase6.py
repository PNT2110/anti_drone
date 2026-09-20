#!/usr/bin/env python3
"""Benchmark one runtime using the fixed Phase 4 replay set."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anti_drone.runtime import DetectorPipeline, make_engine, preprocess  # noqa: E402


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


def temperature_c() -> float | None:
    values = []
    for path in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            values.append(float(path.read_text().strip()) / 1000.0)
        except (OSError, ValueError):
            pass
    return max(values) if values else None


def quantiles(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {"mean_ms": float(array.mean()), "p50_ms": float(np.percentile(array, 50)), "p95_ms": float(np.percentile(array, 95)), "p99_ms": float(np.percentile(array, 99)), "min_ms": float(array.min()), "max_ms": float(array.max())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", choices=("onnx", "ncnn", "tflite"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--input", type=Path, default=Path(".runtime/parity-set"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/benchmarks/pi5-cpu"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--frames", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--nms-iou", type=float, default=0.70)
    args = parser.parse_args()
    images = sorted(path for path in args.input.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not images:
        raise FileNotFoundError(args.input)
    output = args.output_root / args.runtime / args.run_id
    output.mkdir(parents=True, exist_ok=True)
    is_pi = platform.machine() == "aarch64" and any(token in platform.uname().machine.lower() for token in ("aarch64", "arm64"))
    environment = {
        "platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
        "cpu": platform.processor(), "runtime": args.runtime, "model": str(args.model.resolve()),
        "model_sha256": sha256(args.model), "input": str(args.input.resolve()), "input_count": len(images),
        "frames": args.frames, "warmup": args.warmup, "imgsz": args.imgsz, "confidence": args.confidence, "nms_iou": args.nms_iou,
        "is_pi5_candidate": is_pi, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "command": " ".join(sys.argv),
    }
    (output / "environment.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
    process = psutil.Process()
    engine = make_engine(args.runtime, args.model)
    def read_frame(index: int):
        frame = cv2.imread(str(images[index % len(images)]))
        if frame is None:
            raise RuntimeError(f"A replay image could not be read: {images[index % len(images)]}")
        return frame

    for index in range(args.warmup):
        frame = read_frame(index)
        tensor, _, _ = preprocess(frame, args.imgsz)
        engine.infer(tensor)
    model_latencies: list[float] = []
    temperatures: list[str] = []
    runtime_lines = []
    for index in range(1, args.frames + 1):
        frame = read_frame(index - 1)
        tensor, _, _ = preprocess(frame, args.imgsz)
        started = time.perf_counter()
        engine.infer(tensor)
        elapsed = (time.perf_counter() - started) * 1000
        model_latencies.append(elapsed)
        temperatures.append(f"{index},{temperature_c() if temperature_c() is not None else ''}\n")
    pipeline = DetectorPipeline(args.runtime, args.model, args.imgsz, args.confidence, args.nms_iou)
    end_to_end: list[float] = []
    dropped = 0
    for index in range(1, args.frames + 1):
        frame = read_frame(index - 1)
        _, tracks, alerts, elapsed = pipeline.process(frame, index)
        end_to_end.append(elapsed)
        runtime_lines.append(json.dumps({"frame_id": index, "tracks": len(tracks), "alerts": len(alerts), "end_to_end_ms": elapsed, "rss_bytes": process.memory_info().rss}) + "\n")
    model_stats = quantiles(model_latencies)
    end_stats = quantiles(end_to_end)
    benchmark = {
        "status": "DONE_PI" if is_pi else "DONE_HOST_REFERENCE",
        "runtime": args.runtime, "model_only": model_stats, "end_to_end": end_stats,
        "model_only_fps_mean": 1000.0 / model_stats["mean_ms"], "end_to_end_fps_mean": 1000.0 / end_stats["mean_ms"],
        "frames": args.frames, "warmup": args.warmup, "dropped_frames": dropped,
        "rss_bytes_peak": process.memory_info().rss,
        "temperature_c_max": max((float(row.split(",")[1].strip()) for row in temperatures if len(row.split(",")) > 1 and row.split(",")[1].strip()), default=None),
        "pi_acceptance": "eligible" if is_pi else "not_measured_on_raspberry_pi_5",
    }
    (output / "benchmark.json").write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")
    with (output / "per_frame.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame_id", "model_only_ms", "end_to_end_ms"])
        writer.writerows(zip(range(1, args.frames + 1), model_latencies, end_to_end))
    (output / "thermal.log").write_text("frame_id,temp_c\n" + "".join(temperatures), encoding="utf-8")
    (output / "runtime.log").write_text("".join(runtime_lines), encoding="utf-8")
    summary = f"""# Phase 6 benchmark — {args.runtime}

Status: `{benchmark['status']}`

This run used `{args.frames}` replay frames after `{args.warmup}` warm-up frames.

| Measurement | Mean ms | p50 ms | p95 ms | p99 ms | Mean FPS |
|---|---:|---:|---:|---:|---:|
| Model-only | {model_stats['mean_ms']:.3f} | {model_stats['p50_ms']:.3f} | {model_stats['p95_ms']:.3f} | {model_stats['p99_ms']:.3f} | {benchmark['model_only_fps_mean']:.2f} |
| End-to-end | {end_stats['mean_ms']:.3f} | {end_stats['p50_ms']:.3f} | {end_stats['p95_ms']:.3f} | {end_stats['p99_ms']:.3f} | {benchmark['end_to_end_fps_mean']:.2f} |

Hardware class: `{platform.machine()}`. This is a host reference unless the run is executed on Raspberry Pi 5; it must not be copied into a Pi release report.
"""
    (output / "summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps({"output": str(output), **benchmark}, indent=2))


if __name__ == "__main__":
    main()
