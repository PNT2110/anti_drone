"""Compare identity-tracker settings on three full reviewed drone clips.

Detections are computed once per frame. Each tracker candidate receives the
same boxes so identity differences are not confounded by model randomness.
The eight reviewed frames per clip are diagnostic rather than full MOT truth.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
from ultralytics import YOLO

from evaluate_full_video_matrix import STABLE_IDENTITIES, match_pairs, read_labels

try:
    from web.backend.tracker import IdentityTracker
except ImportError:
    from backend.tracker import IdentityTracker


CONFIGS = {
    "baseline": {},
    "ttl_1": {"max_lost_seconds": 1.0},
    "ttl_2": {"max_lost_seconds": 2.0},
    "ttl_6": {"max_lost_seconds": 6.0},
    "appearance_035": {"active_appearance_threshold": 0.35},
    "appearance_050": {"active_appearance_threshold": 0.50},
    "appearance_weight_060": {"active_appearance_weight": 0.60},
    "reid_035": {"reid_match_threshold": 0.35},
    "reid_060": {"reid_match_threshold": 0.60},
    "ttl_2_app_050": {"max_lost_seconds": 2.0, "active_appearance_threshold": 0.50},
}


def evaluate_clip(model, clip, video, labels, imgsz):
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise SystemExit(f"Cannot open {video}")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    sample_indices = {round(i * (frame_count - 1) / 7): i for i in range(8)}
    trackers = {
        name: IdentityTracker(
            **{
                "max_lost_seconds": 4.0,
                "reid_memory_seconds": 60.0,
                "reid_match_threshold": 0.45,
                "min_new_track_confidence": 0.25,
                "confirm_hits": 3,
                **settings,
            },
        )
        for name, settings in CONFIGS.items()
    }
    stats = {
        name: {
            "tp03": 0, "fp03": 0, "fn03": 0,
            "tp05": 0, "fp05": 0, "fn05": 0,
            "track_hits": defaultdict(int),
            "identity_observations": defaultdict(list),
        }
        for name in CONFIGS
    }
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        output = model.predict(frame, imgsz=imgsz, conf=0.10, iou=0.45, verbose=False)[0]
        boxes = output.boxes.xyxy.cpu().numpy().tolist() if output.boxes is not None else []
        scores = output.boxes.conf.cpu().numpy().tolist() if output.boxes is not None else []
        for name, tracker in trackers.items():
            ids = tracker.update(frame, boxes, scores, index / fps)
            shown = [
                {"box": box, "track_id": track_id}
                for box, track_id in zip(boxes, ids) if track_id is not None
            ]
            state = stats[name]
            for prediction in shown:
                state["track_hits"][prediction["track_id"]] += 1
            if index not in sample_indices:
                continue
            truths = labels.get((clip, sample_indices[index]), [])
            for threshold, suffix in ((0.3, "03"), (0.5, "05")):
                pairs = match_pairs(shown, truths, threshold)
                state["tp" + suffix] += len(pairs)
                state["fp" + suffix] += len(shown) - len(pairs)
                state["fn" + suffix] += len(truths) - len(pairs)
                if threshold == 0.3:
                    for pi, ti in pairs:
                        identity = truths[ti]["object"]
                        if identity in STABLE_IDENTITIES[clip]:
                            state["identity_observations"][identity].append({
                                "image_index": sample_indices[index],
                                "track_id": shown[pi]["track_id"],
                            })
        index += 1
        if index % 1000 == 0:
            print(f"{clip}: {index}/{frame_count} frames", flush=True)
    capture.release()
    rows = []
    for name, state in stats.items():
        identities = dict(state["identity_observations"])
        switches = sum(
            left["track_id"] != right["track_id"]
            for observations in identities.values()
            for left, right in zip(observations, observations[1:])
        )
        row = {
            "clip": clip, "config": name, "frames": index,
            "reviewed_identity_switches": switches,
            "reviewed_identity_matches": sum(len(x) for x in identities.values()),
            "observed_sample_ids": identities,
            "unique_ids": len(state["track_hits"]),
            "short_tracks": sum(n < 10 for n in state["track_hits"].values()),
        }
        for suffix in ("03", "05"):
            tp, fp, fn = (state[k + suffix] for k in ("tp", "fp", "fn"))
            precision = tp / max(1, tp + fp)
            recall = tp / max(1, tp + fn)
            row.update({
                "tp" + suffix: tp, "fp" + suffix: fp, "fn" + suffix: fn,
                "precision" + suffix: round(precision, 5),
                "recall" + suffix: round(recall, 5),
                "f1" + suffix: round(2 * precision * recall / max(1e-12, precision + recall), 5),
            })
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--short", type=Path, required=True)
    parser.add_argument("--indoor", type=Path, required=True)
    parser.add_argument("--outdoor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=960)
    args = parser.parse_args()
    model = YOLO(str(args.model), task="detect")
    labels = read_labels(args.labels)
    rows = []
    for clip, video in (("short", args.short), ("indoor", args.indoor), ("outdoor", args.outdoor)):
        rows.extend(evaluate_clip(model, clip, video, labels, args.imgsz))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"model": args.model.name, "configs": CONFIGS, "rows": rows}, indent=2), encoding="utf-8")
    print(f"saved {args.output}", flush=True)


if __name__ == "__main__":
    main()
