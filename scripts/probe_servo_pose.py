#!/usr/bin/env python3
"""Slowly move both commissioned channels to one bounded pose and capture it."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import lgpio


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", default="/dev/video0")
    parser.add_argument("--start-pan", type=int, required=True)
    parser.add_argument("--start-tilt", type=int, required=True)
    parser.add_argument("--target-pan", type=int, required=True)
    parser.add_argument("--target-tilt", type=int, required=True)
    parser.add_argument("--step-us", type=int, default=5)
    parser.add_argument("--interval", type=float, default=0.12)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    cfg = args()
    pulses = (cfg.start_pan, cfg.start_tilt, cfg.target_pan, cfg.target_tilt)
    if not all(900 <= pulse <= 2100 for pulse in pulses):
        raise SystemExit("POSE_PULSE_OUTSIDE_CONSERVATIVE_RANGE")
    if max(abs(cfg.target_pan - cfg.start_pan), abs(cfg.target_tilt - cfg.start_tilt)) > 600:
        raise SystemExit("POSE_DELTA_TOO_LARGE")
    if not 1 <= cfg.step_us <= 10 or cfg.interval < 0.05:
        raise SystemExit("POSE_RAMP_TOO_AGGRESSIVE")

    cfg.output.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(cfg.camera, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 25)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise SystemExit("USB_CAMERA_OPEN_FAILED")

    handle = lgpio.gpiochip_open(0)
    claimed: list[int] = []
    evidence: list[dict] = []
    try:
        for gpio in (12, 13):
            lgpio.gpio_claim_output(handle, gpio, 0)
            claimed.append(gpio)
        span = max(abs(cfg.target_pan - cfg.start_pan), abs(cfg.target_tilt - cfg.start_tilt))
        count = max(1, (span + cfg.step_us - 1) // cfg.step_us)
        for index in range(count + 1):
            ratio = index / count
            pan = round(cfg.start_pan + (cfg.target_pan - cfg.start_pan) * ratio)
            tilt = round(cfg.start_tilt + (cfg.target_tilt - cfg.start_tilt) * ratio)
            for gpio, pulse in ((12, pan), (13, tilt)):
                result = lgpio.tx_servo(handle, gpio, pulse, 50)
                if isinstance(result, int) and result < 0:
                    raise RuntimeError(f"tx_servo GPIO{gpio} failed: {result}")
            time.sleep(cfg.interval)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("USB camera read failed during pose ramp")
            if index in (0, count // 2, count):
                path = cfg.output / f"pose_{index:03d}_pan{pan}_tilt{tilt}.jpg"
                cv2.imwrite(str(path), frame)
                evidence.append({"step": index, "pan_pulse_us": pan, "tilt_pulse_us": tilt, "image": path.name})
        time.sleep(0.5)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("USB camera read failed at final pose")
        final = cfg.output / f"pose_final_pan{cfg.target_pan}_tilt{cfg.target_tilt}.jpg"
        cv2.imwrite(str(final), frame)
        evidence.append({"pan_pulse_us": cfg.target_pan, "tilt_pulse_us": cfg.target_tilt, "image": final.name, "final": True})
        (cfg.output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        return 0
    finally:
        try:
            for gpio in claimed:
                try:
                    lgpio.tx_servo(handle, gpio, 0, 50)
                    lgpio.gpio_write(handle, gpio, 0)
                    lgpio.gpio_free(handle, gpio)
                    lgpio.gpio_claim_input(handle, gpio, lgpio.SET_PULL_NONE)
                    lgpio.gpio_free(handle, gpio)
                except Exception:
                    pass
        finally:
            lgpio.gpiochip_close(handle)
            cap.release()


if __name__ == "__main__":
    raise SystemExit(main())
