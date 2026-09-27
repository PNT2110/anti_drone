#!/usr/bin/env python3
"""Single-axis Scope31 commissioning probe using gpiozero/lgpio on Pi5.

This deliberately does not instantiate the other axis and is not connected to
the detector, tracker, webcam, or ESP32 serial path.  It exists because the
working Pi project uses lgpio software-timed PWM while the RP1 sysfs PWM
channel on this host reports a requested-but-actually-disabled configuration.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

AXES = {"pan": 13, "tilt": 12}
MIN_PULSE_US = 1400
MAX_PULSE_US = 1600
FRAME_WIDTH_S = 0.020
FREQUENCY_HZ = 50


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_log(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, sort_keys=True) + "\n")


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axis", choices=sorted(AXES), required=True)
    parser.add_argument("--pulse-us", type=int, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--accept-unmeasured-supply", action="store_true")
    parser.add_argument("--log", type=Path, default=Path(".runtime/scope31/gpiozero_commissioning.jsonl"))
    args = parser.parse_args()
    if not args.accept_unmeasured_supply:
        parser.error("--accept-unmeasured-supply is required by Scope31R")
    if not MIN_PULSE_US <= args.pulse_us <= MAX_PULSE_US:
        parser.error(f"pulse must be within {MIN_PULSE_US}..{MAX_PULSE_US} us")
    if not 0.05 <= args.duration <= 1.0:
        parser.error("duration must be within 0.05..1.0 seconds")
    return args


def main() -> int:
    args = parse()
    from gpiozero import Device, Servo
    from gpiozero.pins.lgpio import LGPIOFactory

    previous_factory = Device.pin_factory
    factory = LGPIOFactory()
    Device.pin_factory = factory
    servo = None
    gpio = AXES[args.axis]
    value = ((args.pulse_us - MIN_PULSE_US) / (MAX_PULSE_US - MIN_PULSE_US)) * 2.0 - 1.0
    try:
        # Only the explicitly selected GPIO is claimed.
        servo = Servo(
            gpio,
            min_pulse_width=MIN_PULSE_US / 1_000_000,
            max_pulse_width=MAX_PULSE_US / 1_000_000,
            frame_width=FRAME_WIDTH_S,
        )
        servo.value = value
        append_log(args.log, {"event": "gpiozero_lgpio_enabled", "timestamp": now(), "axis": args.axis, "gpio_bcm": gpio, "pulse_us": args.pulse_us, "duration_s": args.duration, "frequency_hz": FREQUENCY_HZ, "backend": "gpiozero_lgpio_tx_pwm", "physical_output": True})
        time.sleep(args.duration)
        return 0
    except KeyboardInterrupt:
        append_log(args.log, {"event": "stop_requested", "timestamp": now(), "axis": args.axis, "reason": "SIGINT"})
        return 130
    finally:
        if servo is not None:
            servo.detach()
        factory.close()
        Device.pin_factory = previous_factory
        append_log(args.log, {"event": "gpiozero_cleanup", "timestamp": now(), "axis": args.axis, "gpio_bcm": gpio, "physical_output": False})


if __name__ == "__main__":
    raise SystemExit(main())
