#!/usr/bin/env python3
"""Pause/step viewer for human identity review; it never writes identity decisions."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def load_boxes(path: Path) -> dict[int, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {int(row["frame_id"]): row for row in rows}


def review(video_path: Path, boxes_path: Path, fps: float = 30.0) -> int:
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - depends on local UI runtime
        raise RuntimeError("OpenCV is required for the interactive review viewer") from exc

    boxes = load_boxes(boxes_path)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = capture.get(cv2.CAP_PROP_FPS) or fps
    frame_index = 0
    playing = False
    print("Controls: Space=pause/play, Right or n=next, Left or b=previous, q=quit")
    try:
        while True:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                break
            frame_id = frame_index + 1
            box = boxes.get(frame_id)
            if box:
                x1, y1 = int(float(box["x1"])), int(float(box["y1"]))
                x2, y2 = int(float(box["x2"])), int(float(box["y2"]))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 255), 2)
                label = f"DRONE | frame={frame_id} | ID=PENDING"
            else:
                label = f"frame={frame_id} | NO SOURCE BOX"
            cv2.putText(frame, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 255), 2)
            cv2.putText(frame, f"{frame_id}/{total}  {'PLAY' if playing else 'PAUSE'}", (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.imshow("Identity review (read-only)", frame)
            delay = max(1, int(1000 / frame_rate)) if playing else 0
            key = cv2.waitKey(delay) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                playing = not playing
            elif key in (ord("n"), 83):
                frame_index = min(frame_index + 1, max(total - 1, 0))
            elif key in (ord("b"), 81):
                frame_index = max(frame_index - 1, 0)
            elif playing:
                frame_index = min(frame_index + 1, max(total - 1, 0))
    finally:
        capture.release()
        cv2.destroyAllWindows()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--boxes", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()
    return review(args.video, args.boxes, args.fps)


if __name__ == "__main__":
    raise SystemExit(main())
