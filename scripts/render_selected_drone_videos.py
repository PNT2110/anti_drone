"""Render reproducible ID-overlay examples with the website detector/tracker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

try:
    from web.backend.detector import YOLODetector
    from web.backend.tracker import create_tracker_from_env
except ImportError:
    from backend.detector import YOLODetector
    from backend.tracker import create_tracker_from_env


def render(detector, source: Path, destination: Path, confidence: float, imgsz: int):
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise SystemExit(f"Cannot open {source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(destination), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        raise SystemExit(f"Cannot write {destination}")
    tracker = create_tracker_from_env()
    seen_ids = set()
    frame_index = 0
    shown_observations = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            result = detector.detect(
                frame, conf=confidence, iou=0.45, imgsz=imgsz,
                tracker=tracker, timestamp=frame_index / fps,
            )
            writer.write(result.annotated_frame)
            ids = [track_id for track_id in result.track_ids if track_id is not None]
            seen_ids.update(ids)
            shown_observations += len(ids)
            frame_index += 1
            if frame_index % 1000 == 0:
                print(f"{source.name}: {frame_index} frames", flush=True)
    finally:
        capture.release()
        writer.release()
    return {
        "source": source.name,
        "output": destination.name,
        "frames": frame_index,
        "unique_ids": len(seen_ids),
        "shown_observations": shown_observations,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--confidence", type=float, default=0.10)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("videos", type=Path, nargs="+")
    args = parser.parse_args()
    detector = YOLODetector(args.model, warmup=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        render(detector, video, args.output_dir / f"{video.stem}_tracked.mp4", args.confidence, args.imgsz)
        for video in args.videos
    ]
    manifest = {
        "model": args.model.name,
        "confidence": args.confidence,
        "imgsz": args.imgsz,
        "videos": outputs,
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
