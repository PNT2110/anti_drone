#!/usr/bin/env python3
"""Offline Mahalanobis-gate sensitivity replay for Scope 09."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import math
import sys
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_scope07_diagnostic import ALERT_CONFIG, EXPECTED_FRAMES, MATCH_IOU_THRESHOLD, PROFILE_NAMES, SEQUENCE_ID, sha256
from scripts.run_scope08_audit import TraceAlert, TraceMotion, load_inputs, switch_events
from anti_drone.tracking import ByteTrackConfig, Detection


EXPERIMENT_PROFILES = ("bytetrack_motion", "bytetrack_motion_adaptive")
GATE_VALUES = (16.0, 25.0, 36.0)
SCOPE08_EXPECTED = {
    "input_audit": "be9ee2f9a03e3585a808db039815fea9e725cf6fc17ca6347c8253c0f43292b7",
    "summary": "b68e17d911dbda809c43fc8d4a500fc62f88ecf1b0cb38511effc65198b29028",
    "bytetrack_motion": "cee8954ba95c3ef11366fa3f7a38c39f252c5715a45f644e616402ce35081f2b",
    "bytetrack_motion_adaptive": "aae09d4e69a338a67ee0d6cf1ac667ec55866bbc8e4aaf011d58f8efb6483877",
}


def iou(first: list[float] | np.ndarray, second: list[float] | np.ndarray) -> float:
    ax1, ay1, ax2, ay2 = map(float, first)
    bx1, by1, bx2, by2 = map(float, second)
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def box(value: np.ndarray | None) -> list[float] | None:
    return [float(item) for item in value.tolist()] if value is not None else None


def snapshots(tracks: dict[int, Any] | list[Any]) -> list[dict[str, Any]]:
    values = tracks.values() if isinstance(tracks, dict) else tracks
    return [{
        "track_id": track.track_id,
        "bbox": box(track.bbox),
        "bbox_observed": box(track.bbox_observed),
        "bbox_predicted": box(track.bbox_predicted),
        "confidence": float(track.confidence),
        "lifecycle": track.state.value,
        "observed": bool(track.is_observed),
        "predicted": not bool(track.is_observed),
        "matched_this_frame": bool(track.matched_this_frame),
        "observation_count": int(track.observation_count),
        "missed": int(track.missed),
        "last_source_frame": track.last_source_frame,
    } for track in values]


def percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
    return {
        "mean": statistics.fmean(values),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
    }


def compare_tracker_rows(current: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches = []
    if len(current) != len(baseline):
        mismatches.append({"reason": "row_count", "current": len(current), "baseline": len(baseline)})
    fields = ("frame_id", "timestamp", "gt_matched_track_id")
    track_fields = ("track_id", "lifecycle", "observed", "predicted", "matched_this_frame", "observation_count", "missed")
    for now, old in zip(current, baseline):
        if any(now[field] != old[field] for field in fields):
            mismatches.append({"frame_id": now.get("frame_id"), "reason": "frame_or_match_field"})
            continue
        now_tracks = [{field: track[field] for field in track_fields} for track in now["tracks"]]
        old_tracks = [{field: track[field] for field in track_fields} for track in old["tracks"]]
        if now_tracks != old_tracks:
            mismatches.append({"frame_id": now.get("frame_id"), "reason": "tracker_state"})
            continue
        for now_track, old_track in zip(now["tracks"], old["tracks"]):
            for field in ("bbox", "bbox_observed", "bbox_predicted", "confidence"):
                a, b = now_track.get(field), old_track.get(field)
                if a is None or b is None:
                    if a != b:
                        mismatches.append({"frame_id": now.get("frame_id"), "reason": field})
                elif not np.allclose(a, b, rtol=0.0, atol=1e-6):
                    mismatches.append({"frame_id": now.get("frame_id"), "reason": field})
    return {"status": "PASS" if not mismatches else "FAIL", "frames_compared": min(len(current), len(baseline)), "mismatches": mismatches[:20]}


def run_gate(profile: str, gate: float, records: list[dict[str, Any]], gt_by_frame: dict[int, dict[str, Any]], output_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = ByteTrackConfig(adaptive_mahalanobis_gate=gate)
    tracker = TraceMotion(config, mode="motion" if profile == "bytetrack_motion" else "motion_adaptive")
    tracker.reset()
    alert = TraceAlert(**ALERT_CONFIG)
    rows = []
    latency: list[float] = []
    previous_ids: set[int] = set()
    for record in records:
        frame_id = int(record["frame_id"])
        timestamp = float(record["timestamp"])
        gt_box = gt_by_frame[frame_id]["bbox"]
        detections = [Detection(np.asarray(item["bbox"], dtype=np.float32), float(item["confidence"]), int(item.get("class_id", 0))) for item in record.get("detections", [])]
        before = snapshots(tracker.tracks)
        start = time.perf_counter()
        tracks = tracker.update(detections, timestamp=timestamp, frame_id=frame_id, source_frame_id=frame_id)
        latency.append((time.perf_counter() - start) * 1000.0)
        alerts, events = alert.update(tracks, timestamp, frame_id)
        current_ids = {track.track_id for track in tracks}
        lifecycle_events = []
        lifecycle_events.extend({"event": "created", "track_id": track_id, "reason": "new_track_from_unmatched_eligible_detection"} for track_id in sorted(current_ids - previous_ids))
        lifecycle_events.extend({"event": "removed", "track_id": track_id, "reason": "lifecycle_timeout_or_track_removal"} for track_id in sorted(previous_ids - current_ids))
        scored = [(iou(track.bbox_observed, gt_box), track) for track in tracks if track.is_observed and track.bbox_observed is not None]
        best_iou, best_track = max(scored, key=lambda item: item[0], default=(0.0, None))
        rows.append({
            "sequence_id": SEQUENCE_ID,
            "frame_id": frame_id,
            "timestamp": timestamp,
            "profile": profile,
            "experiment_gate": gate,
            "ground_truth_bbox": gt_box,
            "detections": [{"bbox": box(np.asarray(item["bbox"], dtype=np.float32)), "confidence": float(item["confidence"]), "gt_iou": iou(item["bbox"], gt_box)} for item in record.get("detections", [])],
            "tracks_before": before,
            "association": tracker.association_trace,
            "tracks": snapshots(tracks),
            "lifecycle_events": lifecycle_events,
            "gt_to_track_iou": best_iou,
            "gt_matched_track_id": best_track.track_id if best_track is not None and best_iou >= MATCH_IOU_THRESHOLD else None,
            "gt_observed": best_track is not None and best_iou >= MATCH_IOU_THRESHOLD,
            "alert_audit": alert.last_trace,
            "tracking_latency_ms": latency[-1],
        })
        previous_ids = current_ids
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    matched_frames = [row["frame_id"] for row in rows if row["gt_observed"]]
    predicted_only = [row["frame_id"] for row in rows if not row["gt_observed"] and any(track["predicted"] for track in row["tracks"])]
    lost = [row["frame_id"] for row in rows if not row["gt_observed"] and not any(track["predicted"] for track in row["tracks"])]
    created_ids = {track["track_id"] for row in rows for track in row["tracks"]}
    id_changes = switch_events(rows)
    non_gt_observations = sum(1 for row in rows for track in row["tracks"] if track["observed"] and iou(track["bbox_observed"], row["ground_truth_bbox"]) < MATCH_IOU_THRESHOLD)
    removed = sum(1 for row in rows for event in row["lifecycle_events"] if event["event"] == "removed")
    alert_events = [event for row in rows for event in row["alert_audit"]["events"]]
    prediction_alerts = [event for event in alert_events if event["predicted"]]
    duplicate_alerts = [row["frame_id"] for row in rows if sum(1 for event in row["alert_audit"]["events"] if event["source_frame_id"] == row["frame_id"]) > 1]
    summary = {
        "profile": profile,
        "gate": gate,
        "configuration": dataclasses.asdict(config),
        "frames": len(rows),
        "detection_frames": sum(1 for row in rows if row["detections"]),
        "observed_gt_frames": len(matched_frames),
        "predicted_only_frames": len(predicted_only),
        "lost_frames": len(lost),
        "track_ids_created": sorted(created_ids),
        "tracks_created": len(created_ids),
        "id_change_count": len(id_changes),
        "id_changes": id_changes,
        "non_gt_observations": non_gt_observations,
        "lifecycle_removed_tracks": removed,
        "alerts": len(alert_events),
        "prediction_only_alerts": len(prediction_alerts),
        "duplicate_alert_source_frames": duplicate_alerts,
        "latency_tracking_only_ms": {**percentiles(latency), "frames": len(latency)},
        "output_jsonl": str(output_path.resolve()),
    }
    return summary, rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/tracking_eval/sequence_001/frame_manifest.csv"))
    parser.add_argument("--ground-truth", type=Path, default=Path("data/tracking_eval/sequence_001/annotations/ground_truth.csv"))
    parser.add_argument("--cache", type=Path, default=Path("data/tracking_eval/sequence_001/detection_cache.onnx.jsonl"))
    parser.add_argument("--identity-validation", type=Path, default=Path("data/tracking_eval/sequence_001/review/identity_review_validation.json"))
    parser.add_argument("--scope07-dir", type=Path, default=Path(".runtime/scope07"))
    parser.add_argument("--scope08-dir", type=Path, default=Path(".runtime/scope08"))
    parser.add_argument("--output-dir", type=Path, default=Path(".runtime/scope09"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    required = [args.manifest, args.ground_truth, args.cache, args.identity_validation, args.scope08_dir / "input_audit.json", args.scope08_dir / "SCOPE08_AUDIT_SUMMARY.json"]
    required += [args.scope08_dir / f"{profile}.jsonl" for profile in EXPERIMENT_PROFILES]
    required += [Path("configs/trackers") / f"{profile}.yaml" for profile in EXPERIMENT_PROFILES]
    missing = [str(path) for path in required if not path.exists()]
    checksums = {str(path): sha256(path) for path in required if path.exists()}
    if missing:
        audit = {"status": "BLOCKED", "errors": [{"code": "missing_artifact", "path": path} for path in missing], "checksums": checksums}
        (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(audit, indent=2))
        return 2
    if checksums[str(args.scope08_dir / "input_audit.json")] != SCOPE08_EXPECTED["input_audit"] or checksums[str(args.scope08_dir / "SCOPE08_AUDIT_SUMMARY.json")] != SCOPE08_EXPECTED["summary"]:
        audit = {"status": "BLOCKED", "errors": [{"code": "scope08_baseline_checksum_mismatch"}], "checksums": checksums}
        (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(audit, indent=2))
        return 2
    try:
        records, gt_by_frame = load_inputs(args.manifest, args.ground_truth, args.cache, args.identity_validation)
    except (RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        audit = {"status": "BLOCKED", "errors": [{"code": "input_validation", "message": str(exc)}], "checksums": checksums}
        (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(audit, indent=2))
        return 2
    scope08_summary = json.loads((args.scope08_dir / "SCOPE08_AUDIT_SUMMARY.json").read_text(encoding="utf-8"))
    if scope08_summary.get("status") != "PASS" or any(item.get("status") != "PASS" for item in scope08_summary.get("instrumentation_comparison", [])):
        audit = {"status": "BLOCKED", "errors": [{"code": "scope08_baseline_not_pass"}], "checksums": checksums}
        (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(audit, indent=2))
        return 2
    audit = {
        "status": "PASS",
        "sequence_id": SEQUENCE_ID,
        "frames": EXPECTED_FRAMES,
        "gate_values_declared_before_replay": list(GATE_VALUES),
        "profiles": list(EXPERIMENT_PROFILES),
        "matching": {"metric": "box IoU", "threshold": MATCH_IOU_THRESHOLD},
        "definitions": {"observed": "track.is_observed and GT IoU >= 0.50", "predicted_only": "no observed GT match and active predicted track", "lost": "no observed GT match and no active predicted track", "id_change": "consecutive GT-matched observations have different tracker IDs", "latency": "time around tracker.update only"},
        "checksums": checksums,
        "scope08_baseline_expected": SCOPE08_EXPECTED,
        "production_config_unchanged": True,
    }
    (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    results = []
    event_rows = []
    baseline_comparison = []
    for profile in EXPERIMENT_PROFILES:
        for gate in GATE_VALUES:
            tag = str(int(gate))
            summary, rows = run_gate(profile, gate, records, gt_by_frame, args.output_dir / f"{profile}_gate{tag}.jsonl")
            results.append(summary)
            for frame_id in (53, 121, 158, 184, 242, 292):
                row = next(item for item in rows if item["frame_id"] == frame_id)
                event_rows.append({
                    "profile": profile,
                    "gate": gate,
                    "frame_id": frame_id,
                    "timestamp": row["timestamp"],
                    "detections": json.dumps(row["detections"]),
                    "tracks_before": json.dumps(row["tracks_before"]),
                    "association": json.dumps(row["association"]),
                    "tracks_after": json.dumps(row["tracks"]),
                    "gt_iou": row["gt_to_track_iou"],
                    "gt_matched_track_id": row["gt_matched_track_id"],
                    "lifecycle_events": json.dumps(row["lifecycle_events"]),
                })
            if gate == 25.0:
                baseline_path = args.scope08_dir / f"{profile}.jsonl"
                baseline_rows = [json.loads(line) for line in baseline_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                baseline_comparison.append({"profile": profile, **compare_tracker_rows(rows, baseline_rows)})
    with (args.output_dir / "event_analysis.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = list(event_rows[0])
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(event_rows)
    report = {
        "status": "PASS" if all(item["status"] == "PASS" for item in baseline_comparison) else "FAIL",
        "input_audit": audit,
        "baseline_gate25_comparison": baseline_comparison,
        "results": results,
        "event_frames": [53, 121, 158, 184, 242, 292],
        "only_changed_parameter": "adaptive_mahalanobis_gate",
        "gate_values": list(GATE_VALUES),
        "production_defaults": dataclasses.asdict(ByteTrackConfig()),
        "scope_boundaries": ["offline cache only", "single sequence", "SPLIT_UNVERIFIED", "no production config change", "no generalization claim"],
    }
    (args.output_dir / "SCOPE09_RESULTS.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
