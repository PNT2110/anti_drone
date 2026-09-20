#!/usr/bin/env python3
"""Run the Phase 5 replay or USB-camera pipeline."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import threading
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anti_drone.runtime import DetectorPipeline  # noqa: E402


class LatestFrame:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.frame = None
        self.frame_id = 0
        self.closed = False

    def put(self, frame) -> None:
        with self.condition:
            self.frame = frame
            self.frame_id += 1
            self.condition.notify()

    def get(self, timeout: float = 1.0):
        with self.condition:
            if self.frame is None and not self.closed:
                self.condition.wait(timeout)
            frame, frame_id = self.frame, self.frame_id
            self.frame = None
            return frame, frame_id

    def close(self) -> None:
        with self.condition:
            self.closed = True
            self.condition.notify_all()


def image_paths(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png"})


def write_environment(path: Path, args: argparse.Namespace) -> None:
    path.write_text(json.dumps({
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "runtime": args.runtime,
        "model": str(args.model.resolve()),
        "input": str(args.input.resolve()) if args.input else None,
        "command": " ".join(sys.argv),
        "timestamp_unix": time.time(),
    }, indent=2) + "\n", encoding="utf-8")


def replay(args: argparse.Namespace) -> int:
    paths = image_paths(args.input)
    if not paths:
        raise FileNotFoundError(f"No replay images in {args.input}")
    if args.max_frames:
        paths = paths[: args.max_frames]
    args.output.mkdir(parents=True, exist_ok=True)
    write_environment(args.output / "environment.json", args)
    pipeline = DetectorPipeline(args.runtime, args.model, args.imgsz, args.confidence, args.nms_iou)
    rows = []
    for frame_id, path in enumerate(paths, start=1):
        frame = cv2.imread(str(path))
        if frame is None:
            raise RuntimeError(f"Cannot read {path}")
        annotated, tracks, alerts, latency = pipeline.process(frame, frame_id)
        cv2.imwrite(str(args.output / path.name), annotated)
        rows.append({"frame_id": frame_id, "image": path.name, "tracks": len(tracks), "alerts": len(alerts), "latency_ms": latency})
    (args.output / "runtime.log").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    latencies = [row["latency_ms"] for row in rows]
    summary = {
        "status": "DONE",
        "mode": "replay",
        "runtime": args.runtime,
        "frames": len(rows),
        "alerts": sum(row["alerts"] for row in rows),
        "mean_latency_ms": sum(latencies) / len(latencies),
        "max_latency_ms": max(latencies),
        "dropped_frames": 0,
        "camera_verified": False,
        "note": "Replay validates model load, preprocessing, NMS, tracker and alert state; it is not a live Pi acceptance test.",
    }
    (args.output / "replay_report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def camera(args: argparse.Namespace) -> int:
    args.output.mkdir(parents=True, exist_ok=True)
    write_environment(args.output / "environment.json", args)
    runtime_log = args.output / "runtime.log"
    runtime_log.write_text("", encoding="utf-8")
    pipeline = DetectorPipeline(args.runtime, args.model, args.imgsz, args.confidence, args.nms_iou)
    latest = LatestFrame()
    capture_done = threading.Event()
    capture_errors: list[str] = []

    def capture_loop() -> None:
        cap = cv2.VideoCapture(args.device)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.camera_height)
        cap.set(cv2.CAP_PROP_FPS, args.camera_fps)
        if not cap.isOpened():
            capture_errors.append(f"camera_open_failed:{args.device}")
            cap.release()
            latest.close()
            return
        disconnects = 0
        while not capture_done.is_set():
            ok, frame = cap.read()
            if ok:
                disconnects = 0
                latest.put(frame)
                continue
            disconnects += 1
            cap.release()
            if disconnects > args.reconnect_attempts:
                capture_errors.append("camera_read_failed_after_reconnect_attempts")
                break
            time.sleep(args.reconnect_delay)
            cap = cv2.VideoCapture(args.device)
            if not cap.isOpened() and disconnects > args.reconnect_attempts:
                capture_errors.append(f"camera_reopen_failed:{args.device}")
                break
        cap.release()
        latest.close()

    thread = threading.Thread(target=capture_loop, daemon=True)
    thread.start()
    started = time.monotonic()
    rows = []
    frame_counter = 0
    processed_log = runtime_log.open("a", encoding="utf-8", buffering=1)
    try:
        while time.monotonic() - started < args.duration_seconds:
            frame, source_id = latest.get(timeout=1.0)
            if frame is None:
                if capture_errors:
                    break
                continue
            frame_counter += 1
            annotated, tracks, alerts, latency = pipeline.process(frame, frame_counter)
            row = {"frame_id": frame_counter, "source_frame_id": source_id, "tracks": len(tracks), "alerts": len(alerts), "latency_ms": latency}
            rows.append(row)
            processed_log.write(json.dumps(row) + "\n")
            if args.show_overlay:
                cv2.imshow("anti-drone", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        capture_done.set()
        latest.close()
        thread.join(timeout=3)
        cv2.destroyAllWindows()
        processed_log.close()
    summary = {
        "status": "DONE" if rows and not capture_errors else "BLOCKED",
        "mode": "camera",
        "runtime": args.runtime,
        "frames": len(rows),
        "alerts": sum(row["alerts"] for row in rows),
        "capture_errors": capture_errors,
        "duration_seconds": time.monotonic() - started,
        "dropped_frames": max(0, (rows[-1]["source_frame_id"] - len(rows)) if rows else 0),
    }
    (args.output / "camera_report.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if summary["status"] == "DONE" else 2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("replay", "camera"))
    parser.add_argument("--runtime", choices=("onnx", "ncnn", "tflite"), required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--nms-iou", type=float, default=0.70)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--camera-width", type=int, default=1280)
    parser.add_argument("--camera-height", type=int, default=720)
    parser.add_argument("--camera-fps", type=int, default=30)
    parser.add_argument("--duration-seconds", type=float, default=30)
    parser.add_argument("--reconnect-attempts", type=int, default=5)
    parser.add_argument("--reconnect-delay", type=float, default=1.0)
    parser.add_argument("--show-overlay", action="store_true")
    args = parser.parse_args()
    if not args.model.exists():
        raise FileNotFoundError(args.model)
    if args.mode == "replay":
        if not args.input:
            raise ValueError("replay requires --input")
        raise SystemExit(replay(args))
    raise SystemExit(camera(args))


if __name__ == "__main__":
    main()
