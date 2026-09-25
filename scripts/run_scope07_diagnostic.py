#!/usr/bin/env python3
"""Run the fixed-input, single-sequence Scope 07 tracking diagnostic."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anti_drone.alerts import TemporalAlert  # noqa: E402
from anti_drone.tracking import ByteTrack, ByteTrackConfig, ByteTrackLegacy, Detection  # noqa: E402


SEQUENCE_ID = "halmstad_v_drone_001"
EXPECTED_FRAMES = 301
MATCH_IOU_THRESHOLD = 0.50
PROFILE_NAMES = ("bytetrack_legacy", "bytetrack_motion", "bytetrack_motion_adaptive")
ALERT_CONFIG = {
    "min_observations": 3,
    "min_high_confidence_observations": 2,
    "confirmation_window_seconds": 0.60,
    "cooldown_seconds": 2.0,
    "high_confidence_threshold": 0.25,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def iou(first: list[float] | np.ndarray, second: list[float] | np.ndarray) -> float:
    ax1, ay1, ax2, ay2 = map(float, first)
    bx1, by1, bx2, by2 = map(float, second)
    ix1, iy1, ix2, iy2 = max(ax1, bx1), max(ay1, by1), min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0.0 else 0.0


def parse_float(value: str, label: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{label} must be finite")
    return parsed


def load_inputs(manifest_path: Path, gt_path: Path, cache_path: Path, validation_path: Path) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], dict[str, Any]]:
    manifest_rows = read_csv(manifest_path)
    gt_rows = read_csv(gt_path)
    cache_rows = [json.loads(line) for line in cache_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if len(manifest_rows) != EXPECTED_FRAMES:
        errors.append(f"manifest rows={len(manifest_rows)}, expected {EXPECTED_FRAMES}")
    manifest_ids = [int(row["frame_id"]) for row in manifest_rows]
    if manifest_ids != list(range(1, EXPECTED_FRAMES + 1)):
        errors.append("manifest frame_id is not exactly 1..301")
    if any(row["sequence_id"] != SEQUENCE_ID for row in manifest_rows):
        errors.append("manifest sequence_id mismatch")

    if len(gt_rows) != EXPECTED_FRAMES:
        errors.append(f"ground truth rows={len(gt_rows)}, expected {EXPECTED_FRAMES}")
    gt_by_frame: dict[int, dict[str, Any]] = {}
    for row in gt_rows:
        frame_id = int(row["frame_id"])
        if frame_id in gt_by_frame:
            errors.append(f"duplicate ground truth frame {frame_id}")
        if row["sequence_id"] != SEQUENCE_ID or row["track_id"] != "1" or row["class_id"] != "0":
            errors.append(f"ground truth identity/schema mismatch at frame {frame_id}")
        box = [parse_float(row[key], f"ground truth {key}") for key in ("x1", "y1", "x2", "y2")]
        if not (0 <= box[0] < box[2] <= 640 and 0 <= box[1] < box[3] <= 512):
            errors.append(f"ground truth box out of bounds at frame {frame_id}")
        gt_by_frame[frame_id] = {"sequence_id": row["sequence_id"], "frame_id": frame_id, "bbox": box, "track_id": 1, "class_id": 0}
    if set(gt_by_frame) != set(manifest_ids):
        errors.append("ground truth frame coverage does not equal manifest")

    if validation.get("status") != "PASS" or validation.get("provenance", {}).get("identity_status") != "VERIFIED":
        errors.append("identity review validation is not PASS/VERIFIED")

    if len(cache_rows) != EXPECTED_FRAMES:
        errors.append(f"detection cache records={len(cache_rows)}, expected {EXPECTED_FRAMES}")
    cache_ids = [int(row.get("frame_id", -1)) for row in cache_rows]
    if cache_ids != manifest_ids:
        errors.append("cache frame order/coverage does not exactly equal manifest")
    for cache, manifest in zip(cache_rows, manifest_rows):
        if cache.get("sequence_id") != SEQUENCE_ID or cache.get("sequence_id") != manifest["sequence_id"]:
            errors.append(f"cache sequence mismatch at frame {manifest['frame_id']}")
        timestamp = parse_float(str(cache.get("timestamp")), f"cache timestamp frame {manifest['frame_id']}")
        manifest_timestamp = parse_float(manifest["timestamp"], f"manifest timestamp frame {manifest['frame_id']}")
        if not math.isclose(timestamp, manifest_timestamp, rel_tol=0.0, abs_tol=1e-6):
            errors.append(f"cache/manifest timestamp mismatch at frame {manifest['frame_id']}")
        detections = cache.get("detections")
        if not isinstance(detections, list):
            errors.append(f"cache detections is not a list at frame {manifest['frame_id']}")
            continue
        for detection in detections:
            box = detection.get("bbox")
            if not isinstance(box, list) or len(box) != 4 or not all(math.isfinite(float(value)) for value in box):
                errors.append(f"invalid cached detection box at frame {manifest['frame_id']}")
            if not math.isfinite(float(detection.get("confidence", float("nan")))):
                errors.append(f"invalid cached confidence at frame {manifest['frame_id']}")

    audit = {
        "status": "PASS" if not errors else "BLOCKED",
        "sequence_id": SEQUENCE_ID,
        "expected_frames": EXPECTED_FRAMES,
        "manifest_frames": len(manifest_rows),
        "ground_truth_frames": len(gt_rows),
        "cache_records": len(cache_rows),
        "identity_validation_status": validation.get("status"),
        "identity_status": validation.get("provenance", {}).get("identity_status"),
        "matching_rule": {"metric": "box IoU", "threshold": MATCH_IOU_THRESHOLD, "declared_before_replay": True},
        "errors": errors,
    }
    if errors:
        raise InputBlocked(audit)
    return cache_rows, gt_by_frame, audit


class InputBlocked(RuntimeError):
    def __init__(self, audit: dict[str, Any]):
        super().__init__("Scope 07 input audit BLOCKED")
        self.audit = audit


def tracker_for(name: str):
    config = ByteTrackConfig()
    if name == "bytetrack_legacy":
        return ByteTrackLegacy(config.track_high_thresh, config.track_low_thresh, config.match_iou, max_lost=15)
    return ByteTrack(config, mode="motion" if name == "bytetrack_motion" else "motion_adaptive")


def detection_list(record: dict[str, Any]) -> list[Detection]:
    return [
        Detection(np.asarray(item["bbox"], dtype=np.float32), float(item["confidence"]), int(item.get("class_id", 0)))
        for item in record.get("detections", [])
    ]


def as_box(value: np.ndarray | None) -> list[float] | None:
    return [float(item) for item in value.tolist()] if value is not None else None


def percentile(values: list[float], fraction: float) -> float:
    return float(np.percentile(values, fraction)) if values else 0.0


def intervals(frame_ids: list[int], records_by_frame: dict[int, dict[str, Any]], observed_frames: list[int]) -> list[dict[str, Any]]:
    if not frame_ids:
        return []
    values = sorted(set(frame_ids))
    groups: list[tuple[int, int]] = []
    start = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            groups.append((start, previous))
            start = value
        previous = value
    groups.append((start, previous))
    result = []
    for start, end in groups:
        recovery = next((frame for frame in observed_frames if frame > end), None)
        result.append({
            "start_frame": start,
            "end_frame": end,
            "start_timestamp": records_by_frame[start]["timestamp"],
            "end_timestamp": records_by_frame[end]["timestamp"],
            "recovery_frame": recovery,
            "recovery_timestamp": records_by_frame[recovery]["timestamp"] if recovery is not None else None,
        })
    return result


def run_profile(name: str, records: list[dict[str, Any]], gt_by_frame: dict[int, dict[str, Any]], output_path: Path) -> dict[str, Any]:
    tracker = tracker_for(name)
    tracker.reset()
    alert = TemporalAlert(**ALERT_CONFIG)
    latencies: list[float] = []
    frame_rows: list[dict[str, Any]] = []
    observed_match_ids: list[int | None] = []
    observed_match_frames: list[int] = []
    predicted_only_frames: list[int] = []
    lost_frames: list[int] = []
    false_positive_track_ids: set[int] = set()
    false_positive_track_frames: list[int] = []
    created_ids: set[int] = set()
    alert_frames: list[int] = []
    prediction_only_alert_frames: list[int] = []
    duplicate_alert_frames: list[int] = []
    records_by_frame = {int(record["frame_id"]): record for record in records}
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            frame_id = int(record["frame_id"])
            timestamp = float(record["timestamp"])
            start = time.perf_counter()
            tracks = tracker.update(detection_list(record), timestamp=timestamp, frame_id=frame_id, source_frame_id=frame_id)
            latencies.append((time.perf_counter() - start) * 1000.0)
            created_ids.update(track.track_id for track in tracks)
            gt_box = gt_by_frame[frame_id]["bbox"]
            observed_candidates = [track for track in tracks if track.is_observed]
            scored = [(iou(track.bbox_observed, gt_box), track) for track in observed_candidates if track.bbox_observed is not None]
            best_iou, best_track = max(scored, key=lambda item: item[0], default=(0.0, None))
            gt_observed = best_track is not None and best_iou >= MATCH_IOU_THRESHOLD
            if gt_observed:
                observed_match_ids.append(best_track.track_id)
                observed_match_frames.append(frame_id)
            else:
                observed_match_ids.append(None)
                active_predictions = [track for track in tracks if not track.is_observed and track.state.value != "REMOVED"]
                if active_predictions:
                    predicted_only_frames.append(frame_id)
                else:
                    lost_frames.append(frame_id)
            for track in tracks:
                track_iou = iou(track.bbox, gt_box)
                if track.is_observed and track_iou < MATCH_IOU_THRESHOLD:
                    false_positive_track_ids.add(track.track_id)
                    false_positive_track_frames.append(frame_id)
            alerts, events = alert.update(tracks, timestamp)
            if events:
                alert_frames.append(frame_id)
            if any(not event_track.is_observed for event_track in alerts):
                prediction_only_alert_frames.append(frame_id)
            if len(events) > 1:
                duplicate_alert_frames.append(frame_id)
            track_output = []
            for track in tracks:
                track_output.append({
                    "track_id": track.track_id,
                    "bbox": as_box(track.bbox),
                    "bbox_observed": as_box(track.bbox_observed),
                    "bbox_predicted": as_box(track.bbox_predicted),
                    "confidence": float(track.confidence),
                    "observed": bool(track.is_observed),
                    "predicted": not bool(track.is_observed),
                    "observation_type": "OBSERVED" if track.is_observed else "PREDICTED",
                    "lifecycle": track.state.value,
                    "matched_this_frame": bool(track.matched_this_frame),
                    "observation_count": int(track.observation_count),
                    "missed": int(track.missed),
                    "last_source_frame": track.last_source_frame,
                    "gt_iou": iou(track.bbox, gt_box),
                })
            event_output = [
                {
                    "event_id": event.event_id,
                    "track_id": event.track_id,
                    "timestamp": event.timestamp,
                    "bbox": list(event.bbox),
                    "confidence": event.confidence,
                    "observation_count": event.observation_count,
                    "source_frame_id": frame_id,
                }
                for event in events
            ]
            frame_rows.append({
                "sequence_id": SEQUENCE_ID,
                "frame_id": frame_id,
                "timestamp": timestamp,
                "input_detection_count": len(record.get("detections", [])),
                "ground_truth_bbox": gt_box,
                "gt_observed": gt_observed,
                "gt_match_track_id": best_track.track_id if gt_observed else None,
                "gt_match_iou": best_iou,
                "tracks": track_output,
                "alerts": event_output,
                "tracking_latency_ms": latencies[-1],
            })
            handle.write(json.dumps(frame_rows[-1], ensure_ascii=False) + "\n")

    id_changes = []
    interruptions = []
    previous_frame = None
    previous_id = None
    for frame_id, current_id in zip(range(1, EXPECTED_FRAMES + 1), observed_match_ids):
        if current_id is None:
            continue
        if previous_id is not None and current_id != previous_id:
            id_changes.append({"from_track_id": previous_id, "to_track_id": current_id, "from_frame": previous_frame, "to_frame": frame_id, "after_gap": frame_id != previous_frame + 1})
        if previous_frame is not None and frame_id != previous_frame + 1:
            interruptions.append({"start_frame": previous_frame + 1, "end_frame": frame_id - 1, "resume_frame": frame_id, "track_id": current_id})
        previous_frame, previous_id = frame_id, current_id
    observed_segments = []
    segment_start = None
    segment_id = None
    for frame_id, current_id in zip(range(1, EXPECTED_FRAMES + 2), observed_match_ids + [None]):
        if current_id != segment_id:
            if segment_id is not None:
                observed_segments.append({"start_frame": segment_start, "end_frame": frame_id - 1, "track_id": segment_id})
            segment_start, segment_id = (frame_id, current_id) if current_id is not None else (None, None)
    summary = {
        "status": "PASS",
        "tracker": name,
        "input_frames": len(records),
        "detection_frames": sum(1 for record in records if record.get("detections")),
        "detection_missing_frame_ids": [int(record["frame_id"]) for record in records if not record.get("detections")],
        "observed_gt_frames": len(observed_match_frames),
        "predicted_only_frames": len(predicted_only_frames),
        "predicted_only_frame_ids": predicted_only_frames,
        "predicted_only_intervals": intervals(predicted_only_frames, records_by_frame, observed_match_frames),
        "lost_frames": len(lost_frames),
        "lost_frame_ids": lost_frames,
        "lost_intervals": intervals(lost_frames, records_by_frame, observed_match_frames),
        "track_ids_created": sorted(created_ids),
        "tracks_created": len(created_ids),
        "observed_identity_segments": observed_segments,
        "identity_interruptions": interruptions,
        "id_changes": id_changes,
        "id_change_count": len(id_changes),
        "false_positive_track_ids": sorted(false_positive_track_ids),
        "false_positive_track_frames": len(false_positive_track_frames),
        "matching": {"metric": "box IoU", "threshold": MATCH_IOU_THRESHOLD},
        "latency_tracking_only_ms": {
            "mean": statistics.fmean(latencies) if latencies else 0.0,
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "frames": len(latencies),
        },
        "alerts": {
            "frames_with_alert": len(alert_frames),
            "alert_frame_ids": alert_frames,
            "prediction_only_alert_frames": prediction_only_alert_frames,
            "duplicate_alert_source_frames": duplicate_alert_frames,
            "config": ALERT_CONFIG,
        },
        "output_jsonl": str(output_path.resolve()),
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/tracking_eval/sequence_001/frame_manifest.csv"))
    parser.add_argument("--ground-truth", type=Path, default=Path("data/tracking_eval/sequence_001/annotations/ground_truth.csv"))
    parser.add_argument("--cache", type=Path, default=Path("data/tracking_eval/sequence_001/detection_cache.onnx.jsonl"))
    parser.add_argument("--identity-validation", type=Path, default=Path("data/tracking_eval/sequence_001/review/identity_review_validation.json"))
    parser.add_argument("--tracker-config-dir", type=Path, default=Path("configs/trackers"))
    parser.add_argument("--output-dir", type=Path, default=Path(".runtime/scope07"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    config_paths = {name: args.tracker_config_dir / f"{name}.yaml" for name in PROFILE_NAMES}
    audit: dict[str, Any]
    try:
        records, gt_by_frame, audit = load_inputs(args.manifest, args.ground_truth, args.cache, args.identity_validation)
    except InputBlocked as blocked:
        audit = blocked.audit
        audit["checksums"] = {"manifest": sha256(args.manifest), "ground_truth": sha256(args.ground_truth), "cache": sha256(args.cache), "identity_validation": sha256(args.identity_validation)}
        (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(audit, indent=2))
        return 2
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        audit = {
            "status": "BLOCKED",
            "sequence_id": SEQUENCE_ID,
            "expected_frames": EXPECTED_FRAMES,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
        (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(audit, indent=2))
        return 2
    missing_configs = [name for name, path in config_paths.items() if not path.exists()]
    if missing_configs:
        audit["status"] = "BLOCKED"
        audit["errors"] = [f"missing tracker configs: {missing_configs}"]
        (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(audit, indent=2))
        return 2
    audit["checksums"] = {
        "manifest": sha256(args.manifest),
        "ground_truth": sha256(args.ground_truth),
        "cache": sha256(args.cache),
        "identity_validation": sha256(args.identity_validation),
        "tracker_configs": {name: sha256(path) for name, path in config_paths.items()},
    }
    audit["tracker_profiles"] = list(PROFILE_NAMES)
    audit["cache_meta_note"] = "Detector-only cache metadata may predate Scope 06; identity authority is the PASS identity validation and official ground truth."
    (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    results = []
    for name in PROFILE_NAMES:
        results.append(run_profile(name, records, gt_by_frame, args.output_dir / f"{name}.jsonl"))
    benchmark = {
        "status": "DONE",
        "diagnostic": "single-sequence tracking diagnostic; not an independent test or general benchmark",
        "sequence_id": SEQUENCE_ID,
        "input_audit": str((args.output_dir / "input_audit.json").resolve()),
        "matching": {"metric": "box IoU", "threshold": MATCH_IOU_THRESHOLD, "declared_before_replay": True},
        "fixed_tracker_profiles": list(PROFILE_NAMES),
        "configuration_checksums": audit["checksums"]["tracker_configs"],
        "results": results,
        "scope_boundaries": ["SPLIT_UNVERIFIED", "no detector rerun", "no tracker/config changes", "no HOTA/IDF1/IDSW computed", "no Pi/camera access"],
    }
    (args.output_dir / "SCOPE07_BENCHMARK.json").write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(benchmark, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
