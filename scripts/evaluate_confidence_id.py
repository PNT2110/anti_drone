"""Sweep YOLO confidence thresholds on labeled video clips and audit track IDs.

This is a diagnostic benchmark, not an independent validation claim: video
provenance must be checked before interpreting the scores as generalization.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

try:
    from web.backend.tracker import IdentityTracker
except ImportError:  # flat copy deployed on the inference server
    from backend.tracker import IdentityTracker


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEQUENCES = [
    ROOT / "data/import_data_rar/legacy_local/tracking_eval" / f"sequence_{index:03d}"
    for index in (1, 2, 3)
]
THRESHOLDS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)


def read_boxes(path: Path) -> dict[int, list[dict]]:
    by_frame: dict[int, list[dict]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            frame_id = int(float(row["frame_id"]))
            box = [float(row[key]) for key in ("x1", "y1", "x2", "y2")]
            identity = row.get("track_id") or row.get("identity_id") or ""
            by_frame[frame_id].append({"box": box, "identity": identity})
    return by_frame


def iou(first: list[float], second: list[float]) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    b = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = a + b - intersection
    return intersection / union if union > 0 else 0.0


def match_frame(predictions: list[dict], truths: list[dict], threshold: float = 0.5):
    candidates = sorted(
        ((iou(pred["box"], truth["box"]), pi, gi)
         for pi, pred in enumerate(predictions)
         for gi, truth in enumerate(truths)),
        reverse=True,
    )
    used_predictions: set[int] = set()
    used_truths: set[int] = set()
    matches = []
    for overlap, pi, gi in candidates:
        if overlap < threshold:
            break
        if pi not in used_predictions and gi not in used_truths:
            matches.append((pi, gi))
            used_predictions.add(pi)
            used_truths.add(gi)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=ROOT / "web/models/drone-yolov8n-fresh-480.pt")
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/video_tests/confidence_id_sweep.json")
    parser.add_argument("sequences", nargs="*", type=Path, default=DEFAULT_SEQUENCES)
    args = parser.parse_args()

    model = YOLO(str(args.model), task="detect")
    records = []
    for sequence_dir in args.sequences:
        video_files = list((sequence_dir / "source").glob("*.mp4"))
        if len(video_files) != 1:
            raise SystemExit(f"Expected exactly one source video in {sequence_dir}")
        gt_path = sequence_dir / "annotations/ground_truth.csv"
        if not gt_path.exists():
            gt_path = sequence_dir / "annotations/source_boxes.csv"
        ground_truth = read_boxes(gt_path)
        capture = cv2.VideoCapture(str(video_files[0]))
        if not capture.isOpened():
            raise SystemExit(f"Cannot open {video_files[0]}")
        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        results = {
            confidence: {
                "raw_tp": 0, "raw_fp": 0, "raw_fn": 0,
                "shown_tp": 0, "shown_fp": 0, "shown_fn": 0, "frames": 0,
                "ids": set(), "identity_assignments": defaultdict(list),
                "tracker": IdentityTracker(
                    max_lost_seconds=4.0, reid_memory_seconds=60.0,
                    reid_match_threshold=0.45, min_new_track_confidence=0.25,
                    confirm_hits=3,
                ),
            }
            for confidence in THRESHOLDS
        }
        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            raw = model.predict(frame, imgsz=args.imgsz, conf=min(THRESHOLDS), iou=0.45, verbose=False)[0]
            raw_boxes = raw.boxes.xyxy.cpu().numpy().tolist() if raw.boxes is not None else []
            raw_scores = raw.boxes.conf.cpu().numpy().tolist() if raw.boxes is not None else []
            truths = ground_truth.get(frame_index + 1, ground_truth.get(frame_index, []))
            timestamp = frame_index / fps
            for confidence, state in results.items():
                selected = [i for i, score in enumerate(raw_scores) if score >= confidence]
                predictions = [
                    {"box": raw_boxes[index], "confidence": float(raw_scores[index])}
                    for index in selected
                ]
                ids = state["tracker"].update(
                    frame, [prediction["box"] for prediction in predictions],
                    [prediction["confidence"] for prediction in predictions], timestamp,
                )
                for prediction, track_id in zip(predictions, ids):
                    prediction["track_id"] = track_id
                    if track_id is not None:
                        state["ids"].add(track_id)
                raw_matches = match_frame(predictions, truths)
                state["raw_tp"] += len(raw_matches)
                state["raw_fp"] += len(predictions) - len(raw_matches)
                state["raw_fn"] += len(truths) - len(raw_matches)
                shown = [prediction for prediction in predictions if prediction["track_id"] is not None]
                state["ids"].update(prediction["track_id"] for prediction in shown)
                matches = match_frame(shown, truths)
                state["shown_tp"] += len(matches)
                state["shown_fp"] += len(shown) - len(matches)
                state["shown_fn"] += len(truths) - len(matches)
                state["frames"] += 1
                for pi, gi in matches:
                    identity = truths[gi]["identity"]
                    track_id = shown[pi]["track_id"]
                    if identity and track_id is not None:
                        state["identity_assignments"][identity].append((frame_index, track_id))
            frame_index += 1
        capture.release()

        for confidence, state in results.items():
            precision = state["shown_tp"] / max(1, state["shown_tp"] + state["shown_fp"])
            recall = state["shown_tp"] / max(1, state["shown_tp"] + state["shown_fn"])
            f1 = 2 * precision * recall / max(1e-12, precision + recall)
            raw_precision = state["raw_tp"] / max(1, state["raw_tp"] + state["raw_fp"])
            raw_recall = state["raw_tp"] / max(1, state["raw_tp"] + state["raw_fn"])
            raw_f1 = 2 * raw_precision * raw_recall / max(1e-12, raw_precision + raw_recall)
            id_switches = 0
            identities = {}
            for identity, observations in state["identity_assignments"].items():
                observations.sort()
                switches = sum(a[1] != b[1] for a, b in zip(observations, observations[1:]))
                id_switches += switches
                identities[identity] = {
                    "tracked_frames": len(observations),
                    "unique_ids": sorted({track_id for _, track_id in observations}),
                    "id_switches": switches,
                }
            records.append({
                "sequence": sequence_dir.name,
                "video": video_files[0].name,
                "annotation": str(gt_path),
                "frames": frame_index,
                "confidence": confidence,
                "iou_threshold": 0.5,
                "shown_tp": state["shown_tp"], "shown_fp": state["shown_fp"], "shown_fn": state["shown_fn"],
                "precision": round(precision, 5), "recall": round(recall, 5),
                "f1": round(f1, 5), "unique_track_ids": len(state["ids"]),
                "raw_tp": state["raw_tp"], "raw_fp": state["raw_fp"], "raw_fn": state["raw_fn"],
                "raw_precision": round(raw_precision, 5), "raw_recall": round(raw_recall, 5),
                "raw_f1": round(raw_f1, 5),
                "verified_identity_switches": id_switches if identities else None,
                "identity_details": identities,
            })
        print(f"finished {sequence_dir.name}: {frame_index} frames", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print("sequence conf shown-P shown-R shown-F1 TP FP FN raw-F1 uniqueIDs ID-switches")
    for row in records:
        print(
            f"{row['sequence']:>12} {row['confidence']:.2f} "
            f"{row['precision']:.3f} {row['recall']:.3f} {row['f1']:.3f} "
            f"{row['shown_tp']} {row['shown_fp']} {row['shown_fn']} {row['raw_f1']:.3f} {row['unique_track_ids']} "
            f"{row['verified_identity_switches']}"
        )
    print(f"saved {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
