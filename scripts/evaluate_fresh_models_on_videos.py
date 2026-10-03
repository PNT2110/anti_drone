"""Sample all freshly trained checkpoints on the two drone review clips."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
from ultralytics import YOLO


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--indoor", type=Path, default=Path("/tmp/indoor_test.mp4"))
    parser.add_argument("--outdoor", type=Path, default=Path("/tmp/outdoor_test.mp4"))
    args = parser.parse_args()

    clips = {
        "indoor": (args.indoor, [0, 17.24, 34.45, 51.69, 68.90, 86.14]),
        "outdoor": (args.outdoor, [0, 4.33, 8.62, 12.95, 17.24, 21.57]),
    }
    for path, _ in clips.values():
        # A missing clip would otherwise be reported as "0 detections".
        if not path.is_file():
            raise SystemExit(f"Cannot open video: {path}")
    model_names = [
        "drone-yolov8n-fresh-480.pt", "drone-yolov8n-fresh-640.pt",
        "drone-yolo11n-fresh-480.pt", "drone-yolo11n-fresh-640.pt",
        "drone-yolo26n-fresh-480.pt", "drone-yolo26n-fresh-640.pt",
    ]
    rows = []
    for model_name in model_names:
        model = YOLO(str(args.models_dir / model_name))
        for clip_name, (path, timestamps) in clips.items():
            capture = cv2.VideoCapture(str(path))
            if not capture.isOpened():
                raise SystemExit(f"Cannot open video: {path}")
            fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            for seconds in timestamps:
                index = min(frame_count - 1, max(0, round(seconds * fps)))
                capture.set(cv2.CAP_PROP_POS_FRAMES, index)
                ok, frame = capture.read()
                if not ok:
                    continue
                result = model.predict(frame, imgsz=args.imgsz, conf=0.25, iou=0.70, verbose=False)[0]
                boxes = []
                if result.boxes is not None:
                    for box, score in zip(result.boxes.xyxy.cpu().numpy(), result.boxes.conf.cpu().numpy()):
                        boxes.append({
                            "xyxy": [round(float(value), 1) for value in box],
                            "conf": round(float(score), 3),
                        })
                rows.append({
                    "model": model_name,
                    "clip": clip_name,
                    "time": seconds,
                    "count": len(boxes),
                    "detections": boxes,
                })
            capture.release()
        del model
        print(f"finished {model_name}", flush=True)

    args.output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for clip_name in clips:
        print(f"[{clip_name}]")
        for time in clips[clip_name][1]:
            values = [r["count"] for r in rows if r["clip"] == clip_name and r["time"] == time]
            print(f"{time:6.2f}s  " + " / ".join(map(str, values)))
    print(f"saved {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
