"""Sweep confidence settings on unlabeled user-uploaded drone videos.

Reports tracker-visible observations and track lifetimes as noise proxies and
creates side-by-side snapshots. Without ground-truth boxes/IDs these are not
precision/recall or IDF1 measurements.
"""

from __future__ import annotations

import argparse
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


THRESHOLDS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)
SNAPSHOT_THRESHOLDS = (0.15, 0.25, 0.35, 0.45, 0.60)


def fit_tile(frame: np.ndarray, width: int = 320, height: int = 180) -> np.ndarray:
    h, w = frame.shape[:2]
    scale = min(width / w, height / h)
    resized = cv2.resize(frame, (round(w * scale), round(h * scale)))
    tile = np.zeros((height, width, 3), dtype=np.uint8)
    y, x = (height - resized.shape[0]) // 2, (width - resized.shape[1]) // 2
    tile[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return tile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("videos", nargs="+", type=Path)
    args = parser.parse_args()

    model = YOLO(str(args.model), task="detect")
    summaries = []
    contact_rows = []
    for video_path in args.videos:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise SystemExit(f"Cannot open video: {video_path}")
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        sample_indices = sorted({
            max(0, min(frame_count - 1, round(frame_count * fraction)))
            for fraction in (0.20, 0.50, 0.80)
        })
        trackers = {
            confidence: IdentityTracker(
                max_lost_seconds=4.0, reid_memory_seconds=60.0,
                reid_match_threshold=0.45, min_new_track_confidence=0.25,
                confirm_hits=3,
            )
            for confidence in THRESHOLDS
        }
        stats = {
            confidence: {
                "candidate_observations": 0, "shown_observations": 0,
                "shown_frames": 0, "max_simultaneous_ids": 0,
                "track_hits": defaultdict(int), "conf_sum": 0.0,
            }
            for confidence in THRESHOLDS
        }
        sampled: dict[tuple[float, int], np.ndarray] = {}
        index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            result = model.predict(frame, imgsz=args.imgsz, conf=min(THRESHOLDS), iou=0.45, verbose=False)[0]
            raw_boxes = result.boxes.xyxy.cpu().numpy().tolist() if result.boxes is not None else []
            raw_scores = result.boxes.conf.cpu().numpy().tolist() if result.boxes is not None else []
            for confidence, tracker in trackers.items():
                selected = [i for i, score in enumerate(raw_scores) if score >= confidence]
                boxes = [raw_boxes[i] for i in selected]
                scores = [float(raw_scores[i]) for i in selected]
                ids = tracker.update(frame, boxes, scores, index / fps)
                visible = [(box, score, track_id) for box, score, track_id in zip(boxes, scores, ids) if track_id is not None]
                item = stats[confidence]
                item["candidate_observations"] += len(boxes)
                item["shown_observations"] += len(visible)
                if visible:
                    item["shown_frames"] += 1
                item["max_simultaneous_ids"] = max(item["max_simultaneous_ids"], len(visible))
                for _, score, track_id in visible:
                    item["track_hits"][track_id] += 1
                    item["conf_sum"] += score
                if index in sample_indices and confidence in SNAPSHOT_THRESHOLDS:
                    annotated = frame.copy()
                    for (x1, y1, x2, y2), score, track_id in visible:
                        p1, p2 = (round(x1), round(y1)), (round(x2), round(y2))
                        cv2.rectangle(annotated, p1, p2, (0, 235, 255), 2)
                        cv2.putText(annotated, f"ID {track_id} {score:.2f}", (p1[0], max(16, p1[1] - 5)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 235, 255), 2, cv2.LINE_AA)
                    sampled[(confidence, index)] = fit_tile(annotated)
            index += 1
            if index % 1000 == 0:
                print(f"{video_path.name}: processed {index}/{frame_count} frames", flush=True)
        cap.release()

        for confidence, item in stats.items():
            track_lengths = list(item["track_hits"].values())
            summaries.append({
                "video": video_path.name,
                "frames": index,
                "duration_seconds": round(index / fps, 2),
                "confidence": confidence,
                "candidate_observations": item["candidate_observations"],
                "shown_observations": item["shown_observations"],
                "unassigned_candidates": item["candidate_observations"] - item["shown_observations"],
                "unique_ids": len(track_lengths),
                "max_simultaneous_ids": item["max_simultaneous_ids"],
                "tracks_under_10_shown_frames": sum(length < 10 for length in track_lengths),
                "mean_shown_confidence": round(item["conf_sum"] / max(1, item["shown_observations"]), 4),
            })

        rows = []
        for confidence in SNAPSHOT_THRESHOLDS:
            cells = [sampled[(confidence, frame_index)] for frame_index in sample_indices]
            rows.append(np.hstack(cells))
        sheet = np.vstack(rows)
        for row_index, confidence in enumerate(SNAPSHOT_THRESHOLDS):
            cv2.putText(sheet, f"conf={confidence:.2f}", (8, row_index * 180 + 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
        args.output.mkdir(parents=True, exist_ok=True)
        sheet_path = args.output / f"{video_path.stem}_confidence_contact.jpg"
        cv2.imwrite(str(sheet_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
        print(f"finished {video_path.name}: {index} frames; contact={sheet_path}", flush=True)

    metrics_path = args.output / "confidence_metrics.json"
    metrics_path.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print("video confidence shown_obs unique_IDs max_simul short_tracks(<10) mean_conf")
    for row in summaries:
        print(f"{row['video']} {row['confidence']:.2f} {row['shown_observations']} "
              f"{row['unique_ids']} {row['max_simultaneous_ids']} "
              f"{row['tracks_under_10_shown_frames']} {row['mean_shown_confidence']:.3f}")
    print(f"saved {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
