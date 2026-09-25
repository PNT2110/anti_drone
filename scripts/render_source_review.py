#!/usr/bin/env python3
"""Render a frame-numbered source-box review video and case list."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--boxes", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=30.0)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    boxes: dict[int, list[dict[str, str]]] = {}
    with args.boxes.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            boxes.setdefault(int(row["frame_id"]), []).append(row)

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {args.video}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(str(args.output_dir / "source_boxes_overlay.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Cannot create review video")

    cases_path = args.output_dir / "review_cases.csv"
    with cases_path.open("w", encoding="utf-8", newline="") as cases_handle:
        cases = csv.DictWriter(cases_handle, fieldnames=["frame_id", "source_frame_index", "timestamp", "category", "status", "reason"])
        cases.writeheader()
        frame_id = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_id += 1
            source_index = frame_id - 1
            timestamp = source_index / args.fps
            for box in boxes.get(frame_id, []):
                x1, y1 = int(round(float(box["x1"]))), int(round(float(box["y1"])))
                x2, y2 = int(round(float(box["x2"]))), int(round(float(box["y2"])))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
                cv2.putText(frame, "DRONE | ID=PENDING", (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 1, cv2.LINE_AA)
            cv2.putText(frame, f"frame_id={frame_id} source_frame_index={source_index} t={timestamp:.3f}s", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
            writer.write(frame)
            cases.writerow({"frame_id": frame_id, "source_frame_index": source_index, "timestamp": f"{timestamp:.9f}", "category": "identity_review", "status": "PENDING", "reason": "Source rectangle exists but MATLAB sidecar contains no track ID; human identity review required."})
    capture.release()
    writer.release()
    (args.output_dir / "README.md").write_text(
        "# Scope 04 review package\n\n"
        "`source_boxes_overlay.mp4` shows the MATLAB source DRONE rectangle and explicit frame IDs.\n"
        "Every frame is listed in `review_cases.csv`; all 301 rows remain `PENDING` because no source track ID exists.\n",
        encoding="utf-8",
    )
    print(f"rendered_frames={frame_id} output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
