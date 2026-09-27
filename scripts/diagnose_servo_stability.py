#!/usr/bin/env python3
"""Measure camera stability with servos off versus holding one fixed pose.

This diagnostic never sweeps an axis.  It uses only the already commissioned
PAN=90/TILT=120 pose, compares image motion/sharpness before, during and after
PWM hold, and always returns both GPIOs to input mode.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "src"))

from anti_drone.servo import (  # noqa: E402
    DirectServoConfig,
    PiDirectServoTransport,
    ServoCommand,
    acquire_runner_lock,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", default="/dev/video0")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=60)
    parser.add_argument("--hardware", action="store_true")
    return parser.parse_args()


def stage(cap, name: str, count: int, output: Path) -> dict:
    sharpness: list[float] = []
    shifts: list[float] = []
    responses: list[float] = []
    previous = None
    started = time.monotonic()
    for index in range(count):
        ok, frame = cap.read()
        if not ok or frame is None or frame.size == 0:
            raise RuntimeError(f"camera read failed during {name}")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sharpness.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        height, width = gray.shape
        roi = gray[0 : max(1, height // 2), width // 3 : max(width // 3 + 1, 5 * width // 6)]
        current = roi.astype(np.float32)
        if previous is not None:
            (dx, dy), response = cv2.phaseCorrelate(previous, current)
            shifts.append(float((dx * dx + dy * dy) ** 0.5))
            responses.append(float(response))
        previous = current
        if index in {0, count // 2, count - 1}:
            cv2.imwrite(str(output / f"{name}_{index:03d}.jpg"), frame)
    elapsed = time.monotonic() - started
    return {
        "samples": count,
        "elapsed_seconds": elapsed,
        "capture_fps": count / max(elapsed, 1e-9),
        "sharpness_laplacian": {
            "median": statistics.median(sharpness),
            "p10": sorted(sharpness)[max(0, int(0.10 * (len(sharpness) - 1)))],
            "minimum": min(sharpness),
        },
        "interframe_phase_shift_pixels": {
            "median": statistics.median(shifts) if shifts else None,
            "p95": sorted(shifts)[int(0.95 * (len(shifts) - 1))] if shifts else None,
            "maximum": max(shifts) if shifts else None,
            "median_response": statistics.median(responses) if responses else None,
        },
    }


def main() -> int:
    args = parse_args()
    if not args.hardware:
        raise SystemExit("EXPLICIT_--hardware_REQUIRED")
    if not 20 <= args.samples <= 300:
        raise SystemExit("SAMPLES_OUTSIDE_SAFE_RANGE")
    args.output.mkdir(parents=True, exist_ok=True)
    lock = acquire_runner_lock(args.output.parent / "anti_drone_tracking.lock")
    cap = cv2.VideoCapture(args.camera, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 25)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        lock.close()
        raise SystemExit("USB_CAMERA_OPEN_FAILED")
    transport = None
    result = {
        "status": "RUNNING",
        "pose": {"pan": 90.0, "tilt": 120.0},
        "movement_policy": "FIXED_POSE_ONLY_NO_SWEEP",
        "stages": {},
    }
    try:
        for _ in range(15):
            if not cap.read()[0]:
                raise RuntimeError("camera warmup failed")
        result["stages"]["pwm_off_before"] = stage(cap, "pwm_off_before", args.samples, args.output)

        transport = PiDirectServoTransport(DirectServoConfig())
        center = ServoCommand(90.0, 120.0)
        transport.send(center)
        time.sleep(0.20)
        transport.send(center)
        time.sleep(0.50)
        result["stages"]["pwm_fixed_hold"] = stage(cap, "pwm_fixed_hold", args.samples, args.output)

        transport.disarm()
        time.sleep(0.50)
        result["stages"]["pwm_off_after"] = stage(cap, "pwm_off_after", args.samples, args.output)
        result["status"] = "SERVO_FIXED_HOLD_DIAGNOSTIC_COMPLETE"
        return 0
    finally:
        if transport is not None:
            transport.close()
        cap.release()
        lock.close()
        (args.output / "servo_stability.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
