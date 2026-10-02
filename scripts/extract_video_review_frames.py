"""Extract a few timestamped frames for reviewing original/annotated videos."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--start", type=float, default=0.0, help="First timestamp in seconds")
    parser.add_argument("--end", type=float, default=None, help="Last timestamp in seconds")
    args = parser.parse_args()

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise SystemExit(f"Cannot open video: {args.video}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0.0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"video={args.video} frames={frame_count} fps={fps:.3f} "
        f"size={width}x{height} duration={duration:.2f}s"
    )

    samples = max(1, args.samples)
    start = max(0.0, min(args.start, duration))
    end = duration if args.end is None else max(start, min(args.end, duration))
    first_index = round(start * fps)
    last_index = min(frame_count - 1, round(end * fps))
    indices = sorted({round(first_index + i * (last_index - first_index) / max(samples - 1, 1)) for i in range(samples)})
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok:
            continue
        seconds = index / fps if fps > 0 else 0.0
        output = args.output_dir / f"{args.video.stem}_{seconds:07.2f}s.jpg"
        if not cv2.imwrite(str(output), frame):
            raise SystemExit(f"Could not write review frame: {output}")
        print(output)

    capture.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
