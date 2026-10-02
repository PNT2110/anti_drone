"""Compare ID stability settings on a local video using one detector pass."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

# Repository layout first; the flat copy on the training server keeps
# backend/ next to this script.
_script_dir = Path(__file__).resolve().parent
tracker_path = _script_dir.parent / "web" / "backend" / "tracker.py"
if not tracker_path.exists():
    tracker_path = _script_dir / "backend" / "tracker.py"
tracker_spec = importlib.util.spec_from_file_location("drone_tracker", tracker_path)
if tracker_spec is None or tracker_spec.loader is None:
    raise RuntimeError(f"Cannot load tracker module: {tracker_path}")
tracker_module = importlib.util.module_from_spec(tracker_spec)
sys.modules[tracker_spec.name] = tracker_module
tracker_spec.loader.exec_module(tracker_module)
IdentityTracker = tracker_module.IdentityTracker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--large-box-area-ratio", type=float, default=0.02)
    parser.add_argument("--large-box-min-conf", type=float, default=0.35)
    args = parser.parse_args()

    settings = {
        "active_app_max_0.45": (4.0, 60.0, 0.45, 0.40, 0.45),
        "active_app_max_0.55": (4.0, 60.0, 0.45, 0.40, 0.55),
        "active_app_max_0.65": (4.0, 60.0, 0.45, 0.40, 0.65),
        "active_app_no_gate": (4.0, 60.0, 0.45, 0.40, 2.0),
    }
    trackers = {
        name: IdentityTracker(max_lost_seconds=active, reid_memory_seconds=memory,
                              reid_match_threshold=threshold,
                              active_appearance_weight=appearance_weight,
                              active_appearance_threshold=appearance_threshold)
        for name, (active, memory, threshold, appearance_weight, appearance_threshold) in settings.items()
    }
    unique = {name: set() for name in settings}
    observations = {name: 0 for name in settings}
    snapshots = {name: [] for name in settings}

    model = YOLO(str(args.model))
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise SystemExit(f"Cannot open video: {args.video}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        result = model.predict(frame, imgsz=args.imgsz, conf=args.conf, iou=0.45, verbose=False)[0]
        boxes = result.boxes.xyxy.cpu().numpy().tolist() if result.boxes is not None else []
        scores = result.boxes.conf.cpu().numpy().tolist() if result.boxes is not None else []
        frame_area = float(frame.shape[0] * frame.shape[1])
        keep = [
            i for i, box in enumerate(boxes)
            if ((box[2] - box[0]) * (box[3] - box[1]) / frame_area <= args.large_box_area_ratio
                or scores[i] >= args.large_box_min_conf)
        ]
        boxes = [boxes[i] for i in keep]
        scores = [scores[i] for i in keep]
        timestamp = index / fps
        for name, tracker in trackers.items():
            ids = tracker.update(frame, boxes, scores, timestamp)
            unique[name].update(track_id for track_id in ids if track_id is not None)
            observations[name] += len(ids)
            if index % max(1, round(fps * 17.0)) == 0 and index > 0:
                snapshots[name].append({
                    "time": round(timestamp, 2),
                    "items": [
                        {"id": track_id, "box": [round(float(v), 1) for v in box]}
                        for box, track_id in zip(boxes, ids)
                    ],
                })
        index += 1
        if index % 500 == 0:
            print(f"processed={index} frames", flush=True)
    capture.release()
    for name in settings:
        print(f"{name}: unique_ids={len(unique[name])}, detections={observations[name]}")
        print("  sampled_ids=" + json.dumps(snapshots[name], separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
