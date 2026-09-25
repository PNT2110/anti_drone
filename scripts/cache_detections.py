#!/usr/bin/env python3
"""Cache detector outputs once so tracker profiles share identical input."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anti_drone.runtime import decode_yolo_output, make_engine, preprocess  # noqa: E402


def image_paths(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", choices=("onnx", "ncnn", "tflite"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.10)
    parser.add_argument("--nms-iou", type=float, default=0.70)
    parser.add_argument("--source-fps", type=float, default=30.0)
    parser.add_argument("--max-frames", type=int, default=0)
    args = parser.parse_args()
    paths = image_paths(args.input)
    if args.max_frames:
        paths = paths[: args.max_frames]
    if not paths:
        raise FileNotFoundError(f"No replay images in {args.input}")
    engine = make_engine(args.runtime, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for frame_id, path in enumerate(paths, start=1):
        frame = cv2.imread(str(path))
        if frame is None:
            raise RuntimeError(f"Cannot read {path}")
        tensor, scale, pad = preprocess(frame, args.imgsz)
        raw = engine.infer(tensor)
        if getattr(engine, "normalized_output", False):
            normalized = raw[0].copy()
            if normalized.ndim == 3 and normalized.shape[1] == 5:
                normalized[:, :4, :] *= args.imgsz
            elif normalized.ndim == 3 and normalized.shape[-1] >= 5:
                normalized[..., :4] *= args.imgsz
            raw[0] = normalized
        decoded = decode_yolo_output(raw[0], frame.shape[:2], scale, pad, args.confidence, args.nms_iou)
        rows.append({
            "sequence_id": args.input.name,
            "frame_id": frame_id,
            "timestamp": frame_id / args.source_fps,
            "image": path.name,
            "detections": [{"bbox": [float(value) for value in detection.box], "confidence": float(detection.confidence), "class_id": detection.class_id} for detection in decoded],
        })
    args.output.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    args.output.with_suffix(args.output.suffix + ".meta.json").write_text(json.dumps({
        "runtime": args.runtime,
        "model": str(args.model.resolve()),
        "input": str(args.input.resolve()),
        "imgsz": args.imgsz,
        "confidence": args.confidence,
        "nms_iou": args.nms_iou,
        "source_fps": args.source_fps,
        "frames": len(rows),
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "DONE", "frames": len(rows), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
