"""Run one fresh model through three full videos at confidence 0.1..1.0.

At eight manually reviewed frames per clip, score only boxes that the website
would display: confirmed boxes carrying an ID. Also record ID continuity for
visually distinguishable drones. The sparse review is diagnostic, not IDF1.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

import cv2
from ultralytics import YOLO

try:
    from web.backend.tracker import IdentityTracker
except ImportError:  # flat copy deployed on the inference server
    from backend.tracker import IdentityTracker


CONFIDENCES = tuple(step / 10 for step in range(1, 11))
IOU_THRESHOLDS = (0.30, 0.50)
STABLE_IDENTITIES = {
    "short": {"drone"},
    "indoor": {"red", "blue", "big"},
    "outdoor": {"drone"},
}


def read_labels(path: Path) -> dict[tuple[str, int], list[dict]]:
    labels: dict[tuple[str, int], list[dict]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            labels[(row["clip"], int(row["image_index"]))].append({
                "object": row["object"],
                "box": [float(row[name]) for name in ("x1", "y1", "x2", "y2")],
            })
    return labels


def iou(first: list[float], second: list[float]) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    b = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = a + b - intersection
    return intersection / union if union > 0 else 0.0


def match_pairs(predictions: list[dict], truths: list[dict], threshold: float) -> list[tuple[int, int]]:
    candidates = sorted(
        ((iou(prediction["box"], truth["box"]), pi, ti)
         for pi, prediction in enumerate(predictions)
         for ti, truth in enumerate(truths)),
        reverse=True,
    )
    matched_predictions: set[int] = set()
    matched_truths: set[int] = set()
    pairs = []
    for overlap, pi, ti in candidates:
        if overlap < threshold:
            break
        if pi not in matched_predictions and ti not in matched_truths:
            pairs.append((pi, ti))
            matched_predictions.add(pi)
            matched_truths.add(ti)
    return pairs


def evaluate_video(model: YOLO, clip: str, video: Path, labels: dict, imgsz: int):
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise SystemExit(f"Cannot open {video}")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    sample_indices = {round(i * (frame_count - 1) / 7): i for i in range(8)}
    trackers = {
        confidence: IdentityTracker(
            max_lost_seconds=4.0, reid_memory_seconds=60.0,
            reid_match_threshold=0.45, min_new_track_confidence=0.25,
            confirm_hits=3,
        )
        for confidence in CONFIDENCES
    }
    stats = {
        confidence: {
            "candidate_observations": 0,
            "shown_observations": 0,
            "max_simultaneous_ids": 0,
            "track_hits": defaultdict(int),
            "sample_scores": {value: {"tp": 0, "fp": 0, "fn": 0} for value in IOU_THRESHOLDS},
            "identity_observations": defaultdict(list),
        }
        for confidence in CONFIDENCES
    }
    index = 0
    inference_seconds = 0.0
    started = time.perf_counter()
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        t0 = time.perf_counter()
        output = model.predict(frame, imgsz=imgsz, conf=0.10, iou=0.45, verbose=False)[0]
        inference_seconds += time.perf_counter() - t0
        raw_boxes = output.boxes.xyxy.cpu().numpy().tolist() if output.boxes is not None else []
        raw_scores = output.boxes.conf.cpu().numpy().tolist() if output.boxes is not None else []
        for confidence, tracker in trackers.items():
            selected = [i for i, score in enumerate(raw_scores) if score + 1e-9 >= confidence]
            boxes = [raw_boxes[i] for i in selected]
            scores = [float(raw_scores[i]) for i in selected]
            track_ids = tracker.update(frame, boxes, scores, index / fps)
            visible = [
                {"box": box, "confidence": score, "track_id": track_id}
                for box, score, track_id in zip(boxes, scores, track_ids)
                if track_id is not None
            ]
            state = stats[confidence]
            state["candidate_observations"] += len(boxes)
            state["shown_observations"] += len(visible)
            state["max_simultaneous_ids"] = max(state["max_simultaneous_ids"], len(visible))
            for prediction in visible:
                state["track_hits"][prediction["track_id"]] += 1
            if index in sample_indices:
                truths = labels.get((clip, sample_indices[index]), [])
                for iou_threshold in IOU_THRESHOLDS:
                    pairs = match_pairs(visible, truths, iou_threshold)
                    scores_at_iou = state["sample_scores"][iou_threshold]
                    scores_at_iou["tp"] += len(pairs)
                    scores_at_iou["fp"] += len(visible) - len(pairs)
                    scores_at_iou["fn"] += len(truths) - len(pairs)
                    if iou_threshold == 0.30:
                        for pi, ti in pairs:
                            identity = truths[ti]["object"]
                            if identity in STABLE_IDENTITIES[clip]:
                                state["identity_observations"][identity].append({
                                    "image_index": sample_indices[index],
                                    "track_id": visible[pi]["track_id"],
                                })
        index += 1
        if index % 1000 == 0:
            print(f"{clip}: {index}/{frame_count} frames", flush=True)
    capture.release()
    elapsed = time.perf_counter() - started

    rows = []
    for confidence, state in stats.items():
        track_lengths = list(state["track_hits"].values())
        observed_ids = dict(state["identity_observations"])
        switches = sum(
            first["track_id"] != second["track_id"]
            for observations in observed_ids.values()
            for first, second in zip(observations, observations[1:])
        )
        for iou_threshold in IOU_THRESHOLDS:
            values = state["sample_scores"][iou_threshold]
            tp, fp, fn = values["tp"], values["fp"], values["fn"]
            precision = tp / max(1, tp + fp)
            recall = tp / max(1, tp + fn)
            f1 = 2 * precision * recall / max(1e-12, precision + recall)
            rows.append({
                "clip": clip, "video": video.name, "frames": index,
                "confidence": confidence, "iou": iou_threshold,
                "tp": tp, "fp": fp, "fn": fn,
                "precision": round(precision, 5), "recall": round(recall, 5), "f1": round(f1, 5),
                "candidate_observations": state["candidate_observations"],
                "shown_observations": state["shown_observations"],
                "unique_ids": len(track_lengths),
                "max_simultaneous_ids": state["max_simultaneous_ids"],
                "tracks_under_10_shown_frames": sum(length < 10 for length in track_lengths),
                "reviewed_identity_switches": switches,
                "reviewed_identity_matches": sum(len(items) for items in observed_ids.values()),
                "observed_sample_ids": observed_ids,
                "inference_ms_per_frame": round(1000 * inference_seconds / max(1, index), 2),
                "total_seconds": round(elapsed, 2),
            })
    print(f"finished {clip}: {index} frames in {elapsed:.1f}s", flush=True)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--short", type=Path, required=True)
    parser.add_argument("--indoor", type=Path, required=True)
    parser.add_argument("--outdoor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=960)
    args = parser.parse_args()

    labels = read_labels(args.labels)
    model = YOLO(str(args.model), task="detect")
    rows = []
    for clip, video in (("short", args.short), ("indoor", args.indoor), ("outdoor", args.outdoor)):
        rows.extend(evaluate_video(model, clip, video, labels, args.imgsz))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"model": args.model.name, "rows": rows}, indent=2), encoding="utf-8")
    print(f"saved {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
