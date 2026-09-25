#!/usr/bin/env python3
"""Read-only root-cause and alert audit for the existing Scope 07 replay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anti_drone.alerts import TemporalAlert  # noqa: E402
from anti_drone.tracking import ByteTrack, ByteTrackConfig, ByteTrackLegacy, Detection  # noqa: E402
from anti_drone.tracking.association import box_iou, normalized_center_distance, valid_box  # noqa: E402
from scripts.run_scope07_diagnostic import (  # noqa: E402
    ALERT_CONFIG,
    EXPECTED_FRAMES,
    MATCH_IOU_THRESHOLD,
    PROFILE_NAMES,
    SEQUENCE_ID,
    sha256,
)


TRACE_WINDOWS = [(50, 55), (118, 124), (130, 160), (180, 187), (239, 246), (289, 295)]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def iou(first: list[float] | np.ndarray, second: list[float] | np.ndarray) -> float:
    return float(box_iou(np.asarray(first, dtype=np.float32), np.asarray(second, dtype=np.float32)))


def detection_classification(confidence: float, *, legacy: bool) -> str:
    if confidence < 0.10:
        return "REJECTED_BEFORE_TRACKER"
    if confidence < 0.25:
        return "LOW_ASSOCIATION"
    if legacy:
        return "HIGH_NEW_TRACK_ELIGIBLE"
    if confidence >= 0.35:
        return "HIGH_NEW_TRACK_ELIGIBLE"
    return "HIGH_NOT_NEW_TRACK_ELIGIBLE"


def jsonable_box(value: np.ndarray | None) -> list[float] | None:
    return [float(item) for item in value.tolist()] if value is not None else None


def tracker_snapshot(tracks: dict[int, Any]) -> list[dict[str, Any]]:
    return [
        {
            "track_id": track.track_id,
            "bbox": jsonable_box(track.bbox),
            "bbox_observed": jsonable_box(track.bbox_observed),
            "bbox_predicted": jsonable_box(track.bbox_predicted),
            "confidence": float(track.confidence),
            "lifecycle": track.state.value,
            "observed": bool(track.is_observed),
            "predicted": not bool(track.is_observed),
            "matched_this_frame": bool(track.matched_this_frame),
            "observation_count": int(track.observation_count),
            "missed": int(track.missed),
            "last_source_frame": track.last_source_frame,
        }
        for track in tracks.values()
    ]


class TraceMotion(ByteTrack):
    """ByteTrack observer; it computes no alternate association result."""

    def __init__(self, config: ByteTrackConfig, mode: str):
        super().__init__(config, mode=mode)
        self.trace_frame_id: int | None = None
        self.associate_call = 0
        self.association_trace: list[dict[str, Any]] = []

    def update(self, detections: list[Detection], timestamp: float, frame_id: int = 0, source_frame_id: int | None = None) -> list[Any]:
        self.trace_frame_id = frame_id
        self.associate_call = 0
        self.association_trace = []
        return super().update(detections, timestamp, frame_id, source_frame_id)

    def _associate(self, track_ids: list[int], detections: list[Detection]):
        self.associate_call += 1
        stage = "HIGH" if self.associate_call == 1 else "LOW"
        local: list[dict[str, Any]] = []
        for track_id in track_ids:
            track = self.tracks[track_id]
            for detection_index, detection in enumerate(detections):
                row: dict[str, Any] = {
                    "frame_id": self.trace_frame_id,
                    "stage": stage,
                    "track_id": track_id,
                    "detection_index": detection_index,
                    "detection_confidence": float(detection.confidence),
                    "track_bbox": jsonable_box(track.bbox_predicted),
                    "detection_bbox": jsonable_box(detection.box),
                    "iou": iou(track.bbox_predicted, detection.box),
                    "mahalanobis": None,
                    "center_distance": None,
                    "gate_pass": False,
                    "rejection_reason": None,
                }
                if not valid_box(detection.box) or not valid_box(track.bbox_predicted):
                    row["rejection_reason"] = "invalid_box"
                else:
                    mahalanobis = float(self.filters[track_id].mahalanobis(detection.box))
                    center = float(normalized_center_distance(track.bbox_predicted, detection.box))
                    row["mahalanobis"] = mahalanobis
                    row["center_distance"] = center
                    reasons = []
                    if self.mode == "motion":
                        if row["iou"] < self.config.match_iou:
                            reasons.append("iou_below_match_iou")
                        if mahalanobis > self.config.adaptive_mahalanobis_gate:
                            reasons.append("mahalanobis_above_gate")
                    else:
                        if mahalanobis > self.config.adaptive_mahalanobis_gate:
                            reasons.append("mahalanobis_above_gate")
                        if row["iou"] < self.config.match_iou and center > self.config.adaptive_center_gate:
                            reasons.append("iou_and_center_gate_rejected")
                    row["gate_pass"] = not reasons
                    row["rejection_reason"] = ";".join(reasons) if reasons else None
                local.append(row)
        pairs, _ = super()._associate(track_ids, detections)
        for row in local:
            row["matched"] = pairs.get(row["track_id"]) == row["detection_index"]
        self.association_trace.extend(local)
        return pairs, _


class TraceLegacy(ByteTrackLegacy):
    """Legacy observer using the same greedy result and a diagnostic score table."""

    def __init__(self, high_threshold: float, low_threshold: float, match_iou: float, max_lost: int = 15):
        super().__init__(high_threshold, low_threshold, match_iou, max_lost=max_lost)
        self.trace_frame_id: int | None = None
        self.association_trace: list[dict[str, Any]] = []
        self.before_snapshot: dict[int, dict[str, Any]] = {}

    def update(self, detections: list[Detection], frame_id: int = 0, timestamp: float | None = None, source_frame_id: int | None = None) -> list[Any]:
        self.trace_frame_id = frame_id
        self.before_snapshot = {track_id: deepcopy(track.__dict__) for track_id, track in self.tracks.items()}
        available = set(range(len(detections)))
        trace: list[dict[str, Any]] = []
        for track_id, state in self.before_snapshot.items():
            track_box = state["bbox_observed"] if state["matched_this_frame"] and state["bbox_observed"] is not None else state["bbox_predicted"]
            candidate_rows = []
            for index in sorted(available):
                score = iou(track_box, detections[index].box)
                candidate_rows.append({
                    "frame_id": frame_id,
                    "stage": "GREEDY_IOU",
                    "track_id": track_id,
                    "detection_index": index,
                    "detection_confidence": float(detections[index].confidence),
                    "track_bbox": jsonable_box(np.asarray(track_box)),
                    "detection_bbox": jsonable_box(detections[index].box),
                    "iou": score,
                    "gate_pass": score >= self.match_iou,
                    "rejection_reason": None if score >= self.match_iou else "iou_below_match_iou",
                })
            trace.extend(candidate_rows)
            if candidate_rows:
                best = max(candidate_rows, key=lambda row: row["iou"])
                for row in candidate_rows:
                    row["greedy_best"] = row is best
        output = super().update(detections, frame_id=frame_id, timestamp=timestamp, source_frame_id=source_frame_id)
        output_by_id = {track.track_id: track for track in output}
        for row in trace:
            track = output_by_id.get(row["track_id"])
            row["matched"] = bool(track is not None and track.is_observed and track.bbox_observed is not None and np.allclose(track.bbox_observed, row["detection_bbox"], atol=1e-5))
        self.association_trace = trace
        return output


class TraceAlert(TemporalAlert):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.last_trace: dict[str, Any] = {}

    def update(self, tracks: list[Any], timestamp: float, source_frame_id: int) -> tuple[list[Any], list[Any]]:
        before_history = {track_id: list(history) for track_id, history in self.history.items()}
        before_seen = {track_id: set(frames) for track_id, frames in self.seen_source_frames.items()}
        alerts, events = super().update(tracks, timestamp)
        event_track_ids = {event.track_id for event in events}
        track_trace = []
        for track in tracks:
            source_frame = track.last_source_frame
            duplicate = source_frame is not None and source_frame in before_seen.get(track.track_id, set())
            if not track.matched_this_frame:
                reason = "prediction_only_skip"
            elif duplicate:
                reason = "duplicate_source_frame_skip"
            elif track.track_id in event_track_ids:
                reason = "alert_policy_satisfied"
            else:
                history = list(self.history.get(track.track_id, []))
                reason = "confirmation_window_or_high_confidence_requirement_not_met"
            track_trace.append({
                "track_id": track.track_id,
                "source_frame_id": source_frame,
                "observed": bool(track.is_observed),
                "predicted": not bool(track.is_observed),
                "matched_this_frame": bool(track.matched_this_frame),
                "duplicate_source_frame": duplicate,
                "history_before": [list(item) for item in before_history.get(track.track_id, [])],
                "history_after": [list(item) for item in self.history.get(track.track_id, [])],
                "reason": reason,
            })
        self.last_trace = {
            "source_frame_id": source_frame_id,
            "timestamp": timestamp,
            "tracks": track_trace,
            "events": [
                {
                    "event_id": event.event_id,
                    "creation_frame": source_frame_id,
                    "source_frame_id": source_frame_id,
                    "timestamp": event.timestamp,
                    "track_id": event.track_id,
                    "observed": True,
                    "predicted": False,
                    "matched_this_frame": True,
                    "bbox": list(event.bbox),
                    "confidence": event.confidence,
                    "observation_count": event.observation_count,
                    "policy": ALERT_CONFIG,
                    "reason": "alert_policy_satisfied",
                }
                for event in events
            ],
        }
        return alerts, events


def make_tracker(name: str):
    config = ByteTrackConfig()
    if name == "bytetrack_legacy":
        return TraceLegacy(config.track_high_thresh, config.track_low_thresh, config.match_iou, max_lost=15)
    return TraceMotion(config, mode="motion" if name == "bytetrack_motion" else "motion_adaptive")


def load_inputs(manifest_path: Path, gt_path: Path, cache_path: Path, validation_path: Path) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    manifest = read_csv(manifest_path)
    gt = read_csv(gt_path)
    cache = [json.loads(line) for line in cache_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    errors = []
    if len(manifest) != EXPECTED_FRAMES or len(gt) != EXPECTED_FRAMES or len(cache) != EXPECTED_FRAMES:
        errors.append(f"lengths manifest/gt/cache={len(manifest)}/{len(gt)}/{len(cache)}")
    if validation.get("status") != "PASS":
        errors.append("identity validator is not PASS")
    if [int(row["frame_id"]) for row in manifest] != list(range(1, EXPECTED_FRAMES + 1)):
        errors.append("manifest frame order mismatch")
    if [int(row["frame_id"]) for row in cache] != list(range(1, EXPECTED_FRAMES + 1)):
        errors.append("cache frame order mismatch")
    if errors:
        raise RuntimeError("; ".join(errors))
    gt_by_frame = {
        int(row["frame_id"]): {
            "bbox": [float(row[key]) for key in ("x1", "y1", "x2", "y2")],
            "track_id": int(row["track_id"]),
            "sequence_id": row["sequence_id"],
        }
        for row in gt
    }
    return cache, gt_by_frame


def verify_expected_checksums(expected: dict[str, Any], current: dict[str, str]) -> list[str]:
    """Return checksum mismatches without mutating or rewriting any input."""

    expected_paths = {
        "manifest": current.get("manifest"),
        "ground_truth": current.get("ground_truth"),
        "cache": current.get("cache"),
        "identity_validation": current.get("identity_validation"),
    }
    errors = []
    for key, actual in expected_paths.items():
        expected_value = expected.get(key)
        if expected_value is not None and actual != expected_value:
            errors.append(f"checksum mismatch for {key}: expected {expected_value}, got {actual}")
    expected_configs = expected.get("tracker_configs", {})
    current_configs = current.get("tracker_configs", {})
    for name, expected_value in expected_configs.items():
        actual = current_configs.get(name)
        if actual != expected_value:
            errors.append(f"checksum mismatch for tracker config {name}: expected {expected_value}, got {actual}")
    return errors


def compare_scope07(profile: str, rows: list[dict[str, Any]], scope07_path: Path) -> dict[str, Any]:
    baseline = [json.loads(line) for line in scope07_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    mismatches = []
    if len(rows) != len(baseline):
        mismatches.append({"reason": "row_count", "instrumented": len(rows), "baseline": len(baseline)})
    for current, previous in zip(rows, baseline):
        if current["frame_id"] != previous["frame_id"] or current["timestamp"] != previous["timestamp"]:
            mismatches.append({"frame_id": current["frame_id"], "reason": "frame_or_timestamp"})
            continue
        current_tracks = [(track["track_id"], track["observed"], track["predicted"], track["lifecycle"], track["matched_this_frame"]) for track in current["tracks"]]
        baseline_tracks = [(track["track_id"], track["observed"], track["predicted"], track["lifecycle"], track["matched_this_frame"]) for track in previous["tracks"]]
        if current_tracks != baseline_tracks:
            mismatches.append({"frame_id": current["frame_id"], "reason": "tracker_output", "instrumented": current_tracks, "baseline": baseline_tracks})
    return {"profile": profile, "status": "PASS" if not mismatches else "FAIL", "frames_compared": min(len(rows), len(baseline)), "mismatches": mismatches[:20]}


def run_profile(name: str, records: list[dict[str, Any]], gt_by_frame: dict[int, dict[str, Any]], output_path: Path, scope07_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tracker = make_tracker(name)
    tracker.reset()
    alert = TraceAlert(**ALERT_CONFIG)
    output_rows = []
    previous_ids: set[int] = set()
    previous_timestamp: float | None = None
    for record in records:
        frame_id = int(record["frame_id"])
        timestamp = float(record["timestamp"])
        gt_box = gt_by_frame[frame_id]["bbox"]
        detections = [Detection(np.asarray(item["bbox"], dtype=np.float32), float(item["confidence"]), int(item.get("class_id", 0))) for item in record.get("detections", [])]
        previous_snapshot = tracker_snapshot(tracker.tracks)
        tracks = tracker.update(detections, timestamp=timestamp, frame_id=frame_id, source_frame_id=frame_id)
        alerts, events = alert.update(tracks, timestamp, frame_id)
        current_ids = {track.track_id for track in tracks}
        created = sorted(current_ids - previous_ids)
        removed = sorted(previous_ids - current_ids)
        lifecycle_events = []
        for track_id in created:
            lifecycle_events.append({"event": "created", "track_id": track_id, "reason": "new_track_from_unmatched_eligible_detection"})
        for track_id in removed:
            gap = None if previous_timestamp is None else timestamp - previous_timestamp
            reason = "timestamp_gap_reset" if gap is not None and gap > 1.0 else "lifecycle_timeout_or_track_removal"
            lifecycle_events.append({"event": "removed", "track_id": track_id, "reason": reason})
        scored = [(iou(track.bbox_observed, gt_box), track) for track in tracks if track.is_observed and track.bbox_observed is not None]
        best_iou, best_track = max(scored, key=lambda item: item[0], default=(0.0, None))
        association_entries = getattr(tracker, "association_trace", [])
        detector_rows = []
        for index, detection in enumerate(detections):
            detector_rows.append({
                "detection_index": index,
                "bbox": jsonable_box(detection.box),
                "confidence": float(detection.confidence),
                "classification": detection_classification(float(detection.confidence), legacy=name == "bytetrack_legacy"),
                "gt_iou": iou(detection.box, gt_box),
            })
        output_rows.append({
            "sequence_id": SEQUENCE_ID,
            "frame_id": frame_id,
            "timestamp": timestamp,
            "ground_truth": {"bbox": gt_box, "track_id": gt_by_frame[frame_id]["track_id"]},
            "detections": detector_rows,
            "tracker_profile": name,
            "tracks_before": previous_snapshot,
            "association": association_entries,
            "tracks": tracker_snapshot({track.track_id: track for track in tracks}),
            "lifecycle_events": lifecycle_events,
            "gt_to_track_iou": best_iou,
            "gt_matched_track_id": best_track.track_id if best_track is not None and best_iou >= MATCH_IOU_THRESHOLD else None,
            "alert_audit": alert.last_trace,
            "previous_timestamp": previous_timestamp,
        })
        previous_ids = current_ids
        previous_timestamp = timestamp
    with output_path.open("w", encoding="utf-8") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    comparison = compare_scope07(name, output_rows, scope07_path)
    return comparison, output_rows


def classify_switch(rows: list[dict[str, Any]], event: dict[str, Any]) -> dict[str, Any]:
    by_frame = {row["frame_id"]: row for row in rows}
    creation_frame = event["new_track_first_observed_frame"]
    creation_row = by_frame[creation_frame]
    association = [entry for entry in creation_row["association"] if entry["track_id"] == event["from_track_id"]]
    reasons = []
    evidence_frames = [creation_frame, event["switch_frame"]]
    if creation_frame != event["switch_frame"]:
        reasons.append("E_GT_IOU_THRESHOLD_CROSSING_AT_REPORTED_SWITCH")
    if association and all(not entry.get("gate_pass", False) for entry in association):
        reasons.append("C_ASSOCIATION_GATE_REJECTED")
        evidence_frames.append(creation_frame)
    if any(item["event"] == "removed" and item["track_id"] == event["from_track_id"] for item in creation_row["lifecycle_events"]):
        reasons.append("D_PREVIOUS_TRACK_REMOVED_BY_LIFECYCLE")
    elif not association and not any(track["track_id"] == event["from_track_id"] for track in creation_row["tracks_before"]):
        reasons.append("D_PREVIOUS_TRACK_NOT_ACTIVE")
    if not reasons:
        reasons.append("G_UNKNOWN_INSUFFICIENT_TRACE")
    event["classification"] = "+".join(reasons)
    event["evidence_frames"] = sorted(set(evidence_frames))
    event["association_evidence"] = association
    return event


def switch_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = [(row["frame_id"], row["gt_matched_track_id"]) for row in rows if row["gt_matched_track_id"] is not None]
    events = []
    for (previous_frame, previous_id), (frame_id, track_id) in zip(matches, matches[1:]):
        if track_id != previous_id:
            first_seen = next((row["frame_id"] for row in rows if any(track["track_id"] == track_id and track["observed"] for track in row["tracks"])), frame_id)
            creation = next((event for row in rows if row["frame_id"] == first_seen for event in row["lifecycle_events"] if event["event"] == "created" and event["track_id"] == track_id), None)
            event = {
                "switch_frame": frame_id,
                "from_frame": previous_frame,
                "from_track_id": previous_id,
                "to_track_id": track_id,
                "new_track_first_observed_frame": first_seen,
                "creation": creation,
                "gap": list(range(previous_frame + 1, frame_id)) if frame_id > previous_frame + 1 else [],
                "classification": "UNKNOWN_UNTIL_TRACE_REVIEW",
            }
            events.append(classify_switch(rows, event))
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/tracking_eval/sequence_001/frame_manifest.csv"))
    parser.add_argument("--ground-truth", type=Path, default=Path("data/tracking_eval/sequence_001/annotations/ground_truth.csv"))
    parser.add_argument("--cache", type=Path, default=Path("data/tracking_eval/sequence_001/detection_cache.onnx.jsonl"))
    parser.add_argument("--identity-validation", type=Path, default=Path("data/tracking_eval/sequence_001/review/identity_review_validation.json"))
    parser.add_argument("--scope07-dir", type=Path, default=Path(".runtime/scope07"))
    parser.add_argument("--output-dir", type=Path, default=Path(".runtime/scope08"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    required = [args.manifest, args.ground_truth, args.cache, args.identity_validation, args.scope07_dir / "input_audit.json"]
    required += [args.scope07_dir / f"{name}.jsonl" for name in PROFILE_NAMES]
    config_paths = {name: Path("configs/trackers") / f"{name}.yaml" for name in PROFILE_NAMES}
    required += list(config_paths.values())
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        audit = {"status": "BLOCKED", "errors": [{"code": "missing_artifact", "path": path} for path in missing]}
        (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(audit, indent=2))
        return 2
    checksums = {str(path): sha256(path) for path in required}
    scope07_audit = json.loads((args.scope07_dir / "input_audit.json").read_text(encoding="utf-8"))
    current_input_checksums = {
        "manifest": sha256(args.manifest),
        "ground_truth": sha256(args.ground_truth),
        "cache": sha256(args.cache),
        "identity_validation": sha256(args.identity_validation),
        "tracker_configs": {name: sha256(path) for name, path in config_paths.items()},
    }
    checksum_errors = verify_expected_checksums(scope07_audit.get("checksums", {}), current_input_checksums)
    if checksum_errors:
        audit = {"status": "BLOCKED", "errors": [{"code": "checksum_mismatch", "message": error} for error in checksum_errors], "checksums": checksums}
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
    audit = {
        "status": "PASS",
        "sequence_id": SEQUENCE_ID,
        "frames": EXPECTED_FRAMES,
        "fixed_matching": {"metric": "box IoU", "threshold": MATCH_IOU_THRESHOLD},
        "trace_windows": [list(window) for window in TRACE_WINDOWS],
        "checksums": checksums,
        "scope07_expected_checksums": scope07_audit.get("checksums", {}),
        "profiles": list(PROFILE_NAMES),
        "scope07_outputs_not_overwritten": True,
    }
    (args.output_dir / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    all_comparisons = []
    all_switches = []
    all_rows: dict[str, list[dict[str, Any]]] = {}
    for name in PROFILE_NAMES:
        comparison, rows = run_profile(name, records, gt_by_frame, args.output_dir / f"{name}.jsonl", args.scope07_dir / f"{name}.jsonl")
        all_comparisons.append(comparison)
        all_rows[name] = rows
        for event in switch_events(rows):
            event["tracker_profile"] = name
            all_switches.append(event)
    with (args.output_dir / "id_switch_events.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["tracker_profile", "switch_frame", "from_frame", "from_track_id", "to_track_id", "new_track_first_observed_frame", "gap", "classification"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for event in all_switches:
            writer.writerow({field: json.dumps(event[field]) if isinstance(event[field], list) else event[field] for field in fields})
    summary = {
        "status": "PASS" if all(item["status"] == "PASS" for item in all_comparisons) else "FAIL",
        "input_audit": audit,
        "instrumentation_comparison": all_comparisons,
        "id_switch_events": all_switches,
        "trace_windows": [list(window) for window in TRACE_WINDOWS],
        "alert_invariant": {
            "prediction_only_creates_observation": False,
            "duplicate_source_frame_creates_observation": False,
            "source_frame_is_explicit_in_event_trace": True,
        },
        "note": "Root-cause labels remain UNKNOWN until the generated traces are reviewed; no algorithmic conclusion is inferred by this harness.",
    }
    (args.output_dir / "SCOPE08_AUDIT_SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
