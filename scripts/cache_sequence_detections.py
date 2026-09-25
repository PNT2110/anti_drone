#!/usr/bin/env python3
"""Cache detector outputs for a prepared continuous video sequence."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anti_drone.runtime import decode_yolo_output, make_engine, preprocess  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--runtime", choices=("onnx", "ncnn", "tflite"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.10)
    parser.add_argument("--nms-iou", type=float, default=0.70)
    parser.add_argument("--max-frames", type=int, default=0)
    args = parser.parse_args()

    with args.manifest.open("r", encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    if args.max_frames:
        manifest_rows = manifest_rows[: args.max_frames]
    if not manifest_rows:
        raise ValueError("The sequence manifest contains no frames")

    engine = make_engine(args.runtime, args.model)
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open sequence video: {args.video}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for expected in manifest_rows:
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"Video ended before manifest frame {expected['frame_id']}")
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
            "sequence_id": expected["sequence_id"],
            "frame_id": int(expected["frame_id"]),
            "source_frame_index": int(expected["source_frame_index"]),
            "timestamp": float(expected["timestamp"]),
            "image": args.video.name,
            "detections": [
                {"bbox": [float(value) for value in detection.box], "confidence": float(detection.confidence), "class_id": detection.class_id}
                for detection in decoded
            ],
        })
    capture.release()
    args.output.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    meta = {
        "status": "DONE",
        "runtime": args.runtime,
        "model": str(args.model.resolve()),
        "manifest": str(args.manifest.resolve()),
        "video": str(args.video.resolve()),
        "imgsz": args.imgsz,
        "confidence": args.confidence,
        "nms_iou": args.nms_iou,
        "frames": len(rows),
        "identity_ground_truth": "pending",
        "note": "Detections are detector outputs only; no tracker IDs or pseudo ground truth are included.",
    }
    args.output.with_suffix(args.output.suffix + ".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
