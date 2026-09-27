#!/usr/bin/env python3
"""Slow, single-axis servo pulse probe with camera evidence.

It ramps one explicitly selected GPIO from a known current pulse to a nearby
candidate pulse, saves webcam frames along the way, and always disables
PWM/returns that line to input on completion or failure.  The other axis is
never claimed.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import lgpio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", default="/dev/video0")
    parser.add_argument("--gpio", type=int, default=13)
    parser.add_argument("--start-pulse", type=int, required=True)
    parser.add_argument("--end-pulse", type=int, required=True)
    parser.add_argument("--step-us", type=int, default=5)
    parser.add_argument("--interval", type=float, default=0.10)
    parser.add_argument("--snapshot-every-us", type=int, default=25)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.gpio not in (12, 13):
        raise SystemExit("SERVO_CALIBRATION_REQUIRES_GPIO12_OR_GPIO13")
    # 2300 us was reached on the installed tilt axis with camera, USB and Pi
    # power stable. Permit only one additional bounded calibration segment;
    # this is still not a generic MG90S full-range sweep.
    if not (900 <= args.start_pulse <= 2350 and 900 <= args.end_pulse <= 2350):
        raise SystemExit("PULSE_OUTSIDE_CONSERVATIVE_PROBE_RANGE")
    if args.step_us < 1 or args.step_us > 10 or args.interval < 0.05:
        raise SystemExit("RAMP_TOO_AGGRESSIVE")

    args.output.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(args.camera, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 25)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise SystemExit("USB_CAMERA_OPEN_FAILED")

    handle = lgpio.gpiochip_open(0)
    claimed = False
    evidence: list[dict] = []
    try:
        lgpio.gpio_claim_output(handle, args.gpio, 0)
        claimed = True
        direction = 1 if args.end_pulse >= args.start_pulse else -1
        step = direction * args.step_us
        pulses = list(range(args.start_pulse, args.end_pulse, step)) + [args.end_pulse]
        last_snapshot = None
        axis_name = "pan" if args.gpio == 12 else "tilt"
        for pulse in pulses:
            result = lgpio.tx_servo(handle, args.gpio, pulse, 50)
            if isinstance(result, int) and result < 0:
                raise RuntimeError(f"tx_servo failed: {result}")
            time.sleep(args.interval)
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("USB camera read failed during tilt ramp")
            if (
                last_snapshot is None
                or abs(pulse - last_snapshot) >= args.snapshot_every_us
                or pulse == args.end_pulse
            ):
                path = args.output / f"{axis_name}_{pulse:04d}us.jpg"
                if not cv2.imwrite(str(path), frame):
                    raise RuntimeError(f"failed to write {path}")
                evidence.append({"pulse_us": pulse, "image": path.name})
                last_snapshot = pulse
        time.sleep(0.4)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("USB camera read failed at final tilt pulse")
        final_path = args.output / f"{axis_name}_{args.end_pulse:04d}us_final.jpg"
        cv2.imwrite(str(final_path), frame)
        evidence.append({"pulse_us": args.end_pulse, "image": final_path.name, "final": True})
        (args.output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
        return 0
    finally:
        try:
            if claimed:
                # This Raspberry Pi OS lgpio build rejects the documented
                # tx_servo(..., pulse_width=0) stop request. Releasing the
                # line cancels its queued PWM; then briefly claim it as input
                # so cleanup has a hardware-verifiable safe end state.
                lgpio.gpio_free(handle, args.gpio)
                lgpio.gpio_claim_input(handle, args.gpio, lgpio.SET_PULL_NONE)
                lgpio.gpio_free(handle, args.gpio)
        finally:
            lgpio.gpiochip_close(handle)
            cap.release()


if __name__ == "__main__":
    raise SystemExit(main())
