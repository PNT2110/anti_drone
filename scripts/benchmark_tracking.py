#!/usr/bin/env python3
"""Benchmark tracking-only behavior from a JSON/JSONL/CSV detection stream.

The detector and image decoding are deliberately excluded.  Each record must
contain ``frame_id``, optionally ``timestamp`` and either a ``detections``
array or one ``bbox`` plus ``confidence``.  This makes the benchmark portable
to a Pi without requiring a model or camera.
"""

from __future__ import annotations

import argparse
import csv
import json
import resource
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anti_drone.tracking import ByteTrack, ByteTrackConfig, ByteTrackLegacy, Detection  # noqa: E402


def load_records(path: Path, source_fps: float) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            raw = list(csv.DictReader(handle))
        records = []
        for row in raw:
            records.append({
                "frame_id": int(row["frame_id"]),
                "timestamp": float(row.get("timestamp") or int(row["frame_id"]) / source_fps),
                "detections": [{"bbox": json.loads(row["bbox"]), "confidence": float(row["confidence"]), "class_id": int(row.get("class_id") or 0)}],
            })
        return records
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        with path.open(encoding="utf-8") as handle:
            payload = [json.loads(line) for line in handle if line.strip()]
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("frames", payload.get("records", []))
    records = []
    for index, item in enumerate(payload, start=1):
        record = dict(item)
        record.setdefault("frame_id", index)
        record.setdefault("timestamp", float(record["frame_id"]) / source_fps)
        if "detections" not in record:
            record["detections"] = [{"bbox": record.get("bbox"), "confidence": record.get("confidence", 0.0), "class_id": record.get("class_id", 0)}]
        records.append(record)
    return records


def detections(record: dict) -> list[Detection]:
    result = []
    for item in record.get("detections", []):
        box = item.get("bbox")
        if box is None:
            continue
        result.append(Detection(np.asarray(box, dtype=np.float32), float(item.get("confidence", 0.0)), int(item.get("class_id", 0))))
    return result


def tracker_for(name: str):
    config = ByteTrackConfig()
    if name == "bytetrack_legacy":
        return ByteTrackLegacy(config.track_high_thresh, config.track_low_thresh, config.match_iou)
    return ByteTrack(config, mode="motion" if name == "bytetrack_motion" else "motion_adaptive")


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(values, fraction))


def run(name: str, records: list[dict], drop_every: int) -> dict:
    tracker = tracker_for(name)
    latencies = []
    emitted_ids: set[tuple[str, int]] = set()
    processed = 0
    dropped = 0
    previous_source = None
    current_sequence = None
    sequences: set[str] = set()
    sequence_resets = 0
    started_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    status = "DONE"
    error = None
    for index, record in enumerate(records, start=1):
        if drop_every and index % drop_every == 0:
            continue
        try:
            sequence_id = str(record.get("sequence_id", "default"))
            if current_sequence is None:
                current_sequence = sequence_id
                sequences.add(sequence_id)
            elif sequence_id != current_sequence:
                tracker.reset()
                previous_source = None
                current_sequence = sequence_id
                sequences.add(sequence_id)
                sequence_resets += 1
            timestamp = float(record["timestamp"])
            source_frame = int(record["frame_id"])
            start = time.perf_counter()
            tracks = tracker.update(detections(record), timestamp=timestamp, frame_id=processed + 1, source_frame_id=source_frame)
            latencies.append((time.perf_counter() - start) * 1000.0)
        except Exception as exc:  # keep all tracker results in one report
            status = "ERROR"
            error = f"{type(exc).__name__}: {exc}"
            break
        processed += 1
        emitted_ids.update((current_sequence, track.track_id) for track in tracks)
        if previous_source is not None and source_frame > previous_source + 1:
            dropped += source_frame - previous_source - 1
        previous_source = source_frame
    ending_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "status": status,
        "error": error,
        "tracker": name,
        "frames_processed": processed,
        "input_records": len(records),
        "sequences_processed": len(sequences),
        "sequence_resets": sequence_resets,
        "dropped_source_frames": dropped,
        "tracks_created": len(emitted_ids),
        "latency_ms": {"mean": statistics.fmean(latencies) if latencies else 0.0, "p50": percentile(latencies, 50), "p95": percentile(latencies, 95), "p99": percentile(latencies, 99)},
        "memory_overhead_kb_peak_delta": max(0, ending_rss - started_rss),
        "ground_truth_metrics": None,
        "ground_truth_note": "No identity ground truth was supplied; this is a tracking-only latency/lifecycle benchmark.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-fps", type=float, default=30.0)
    parser.add_argument("--drop-every", type=int, default=0, help="Skip every Nth input record to replay dropped frames")
    parser.add_argument("--trackers", nargs="+", choices=("bytetrack_legacy", "bytetrack_motion", "bytetrack_motion_adaptive"), default=["bytetrack_legacy", "bytetrack_motion", "bytetrack_motion_adaptive"])
    args = parser.parse_args()
    if args.drop_every < 0:
        raise ValueError("--drop-every must be non-negative")
    records = load_records(args.input, args.source_fps)
    report = {"status": "DONE", "input": str(args.input), "records": len(records), "results": [run(name, records, args.drop_every) for name in args.trackers]}
    report["sequence_count"] = len({record.get("sequence_id", "default") for record in records})
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
