#!/usr/bin/env python3
"""Bounded, manual MG90S commissioning on Raspberry Pi 5.

This tool is intentionally separate from the detector/tracker runtime.  It
drives at most one explicitly selected PWM channel for a finite duration and
always disables/unexports the channel on normal exit, Ctrl+C, or exception.
The external supply voltage is deliberately represented as unmeasured; the
operator must explicitly acknowledge the Scope31R waiver.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PWMCHIP = Path("/sys/class/pwm/pwmchip0")
PWM_PERIOD_NS = 20_000_000
PWM_FREQUENCY_HZ = 50
COMMISSIONING_MIN_US = 1400
COMMISSIONING_MAX_US = 1600
MAX_DURATION_S = 2.0
PIN_ALT = "a0"
SUPPLY_STATUS = "POWER_VOLTAGE_UNMEASURED_USER_ACCEPTED"

AXES = {
    "pan": {"gpio": 13, "channel": 1},
    "tilt": {"gpio": 12, "channel": 0},
}


class CommissioningError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pulse_us_to_ns(pulse_us: int) -> int:
    return pulse_us * 1_000


def run_pinctrl(*args: str) -> str:
    result = subprocess.run(
        ["pinctrl", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def log_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


@dataclass
class PwmChannel:
    axis: str
    gpio: int
    channel: int
    log_path: Path
    exported_here: bool = False
    pinmux_set_here: bool = False
    enabled: bool = False

    @property
    def path(self) -> Path:
        return PWMCHIP / f"pwm{self.channel}"

    def _write(self, name: str, value: str) -> None:
        (self.path / name).write_text(value, encoding="ascii")

    def _read(self, name: str) -> str:
        return (self.path / name).read_text(encoding="ascii").strip()

    def setup_without_enable(self) -> None:
        if os.geteuid() != 0:
            raise CommissioningError(
                "SERVO_PWM_BACKEND_BLOCKED:root_privilege_required_for_sysfs_pwm"
            )
        if not PWMCHIP.exists():
            raise CommissioningError("SERVO_PWM_BACKEND_BLOCKED:pwmchip0_missing")
        if self.path.exists():
            enabled = self._read("enable")
            raise CommissioningError(
                f"SERVO_PWM_BACKEND_BLOCKED:pwm{self.channel}_already_exported_enable={enabled}"
            )
        (PWMCHIP / "export").write_text(str(self.channel), encoding="ascii")
        deadline = time.monotonic() + 1.0
        while not self.path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not self.path.exists():
            raise CommissioningError(f"SERVO_PWM_BACKEND_BLOCKED:pwm{self.channel}_export_timeout")
        self.exported_here = True
        try:
            self._write("enable", "0")
            self._write("period", str(PWM_PERIOD_NS))
            self._write("duty_cycle", "0")
            # On RP1, both requested pins expose PWM0 on alternate function 0.
            run_pinctrl("set", str(self.gpio), PIN_ALT)
            self.pinmux_set_here = True
            state = run_pinctrl("get", str(self.gpio))
            if "none" in state.lower() or "input" in state.lower():
                raise CommissioningError(f"SERVO_PWM_BACKEND_BLOCKED:pinmux_not_pwm:{state}")
        except BaseException:
            try:
                self.disable("setup_failure_before_motion")
            except BaseException:
                pass
            raise
        log_event(
            self.log_path,
            {
                "event": "pwm_setup_no_enable",
                "timestamp": utc_now(),
                "axis": self.axis,
                "gpio_bcm": self.gpio,
                "pwm_channel": self.channel,
                "period_ns": PWM_PERIOD_NS,
                "frequency_hz": PWM_FREQUENCY_HZ,
                "supply_status": SUPPLY_STATUS,
                "physical_output": False,
            },
        )

    def command(self, pulse_us: int, duration_s: float) -> None:
        self._write("duty_cycle", str(pulse_us_to_ns(pulse_us)))
        self._write("enable", "1")
        self.enabled = True
        log_event(
            self.log_path,
            {
                "event": "pwm_enabled_bounded_command",
                "timestamp": utc_now(),
                "axis": self.axis,
                "gpio_bcm": self.gpio,
                "pwm_channel": self.channel,
                "pulse_us": pulse_us,
                "duration_s": duration_s,
                "period_ns": PWM_PERIOD_NS,
                "frequency_hz": PWM_FREQUENCY_HZ,
                "supply_status": SUPPLY_STATUS,
                "physical_output": True,
            },
        )
        time.sleep(duration_s)

    def disable(self, reason: str) -> None:
        errors: list[str] = []
        if self.path.exists():
            try:
                self._write("enable", "0")
                self.enabled = False
            except OSError as exc:
                errors.append(f"disable:{exc}")
            try:
                self._write("duty_cycle", "0")
            except OSError as exc:
                errors.append(f"duty:{exc}")
        if self.pinmux_set_here:
            try:
                run_pinctrl("set", str(self.gpio), "no")
            except (OSError, subprocess.CalledProcessError) as exc:
                errors.append(f"pinmux:{exc}")
            self.pinmux_set_here = False
        if self.exported_here and self.path.exists():
            try:
                (PWMCHIP / "unexport").write_text(str(self.channel), encoding="ascii")
            except OSError as exc:
                errors.append(f"unexport:{exc}")
            self.exported_here = False
        log_event(
            self.log_path,
            {
                "event": "emergency_disable_cleanup",
                "timestamp": utc_now(),
                "axis": self.axis,
                "gpio_bcm": self.gpio,
                "pwm_channel": self.channel,
                "reason": reason,
                "errors": errors,
                "physical_output": False,
            },
        )
        if errors:
            raise CommissioningError("SERVO_PWM_CLEANUP_FAILED:" + ";".join(errors))


def validate_args(args: argparse.Namespace) -> None:
    if args.axis is None:
        return
    if args.pulse_us is None or args.duration is None:
        raise CommissioningError("explicit --pulse-us and --duration are required")
    if not COMMISSIONING_MIN_US <= args.pulse_us <= COMMISSIONING_MAX_US:
        raise CommissioningError(
            f"PULSE_OUTSIDE_BOUNDED_RANGE:{COMMISSIONING_MIN_US}-{COMMISSIONING_MAX_US}us"
        )
    if not 0.05 <= args.duration <= MAX_DURATION_S:
        raise CommissioningError(f"DURATION_OUTSIDE_BOUNDED_RANGE:0.05-{MAX_DURATION_S}s")
    if not args.accept_unmeasured_supply:
        raise CommissioningError("POWER_VOLTAGE_UNMEASURED_USER_ACCEPTED flag required")


def run_single(args: argparse.Namespace) -> int:
    info = AXES[args.axis]
    pwm = PwmChannel(args.axis, info["gpio"], info["channel"], args.log)
    try:
        pwm.setup_without_enable()
        pwm.command(args.pulse_us, args.duration)
        return 0
    except KeyboardInterrupt:
        log_event(args.log, {"event": "stop_requested", "timestamp": utc_now(), "reason": "SIGINT"})
        return 130
    except BaseException as exc:
        log_event(
            args.log,
            {"event": "exception_stop_requested", "timestamp": utc_now(), "reason": repr(exc)},
        )
        raise
    finally:
        pwm.disable("normal_exit_or_exception")


def run_sequence(args: argparse.Namespace) -> int:
    sequences = {
        "small": [1500, 1450, 1500, 1550, 1500],
        "optional": [1500, 1400, 1500, 1600, 1500],
    }
    if args.sequence not in sequences:
        raise CommissioningError("unknown sequence")
    info = AXES[args.axis]
    pwm = PwmChannel(args.axis, info["gpio"], info["channel"], args.log)
    try:
        pwm.setup_without_enable()
        for pulse in sequences[args.sequence]:
            pwm.command(pulse, args.step_duration)
            pwm._write("enable", "0")
            pwm.enabled = False
            time.sleep(args.pause)
        return 0
    except KeyboardInterrupt:
        log_event(args.log, {"event": "stop_requested", "timestamp": utc_now(), "reason": "SIGINT"})
        return 130
    finally:
        pwm.disable("sequence_exit_or_exception")


def disable_all(log_path: Path) -> int:
    for axis, info in AXES.items():
        pwm = PwmChannel(axis, info["gpio"], info["channel"], log_path)
        pwm.exported_here = (pwm.path).exists()
        pwm.pinmux_set_here = True
        try:
            pwm.disable("explicit_disable_all")
        except CommissioningError:
            # Continue disabling the other channel, then report failure.
            continue
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--axis", choices=sorted(AXES))
    p.add_argument("--pulse-us", type=int)
    p.add_argument("--duration", type=float)
    p.add_argument("--sequence", choices=("small", "optional"))
    p.add_argument("--step-duration", type=float, default=0.35)
    p.add_argument("--pause", type=float, default=0.20)
    p.add_argument("--disable-all", action="store_true")
    p.add_argument("--accept-unmeasured-supply", action="store_true")
    p.add_argument("--log", type=Path, default=Path(".runtime/scope31/servo_commissioning.jsonl"))
    return p


def install_stop_handlers() -> None:
    def stop_handler(signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)


def main() -> int:
    install_stop_handlers()
    args = parser().parse_args()
    if args.disable_all:
        return disable_all(args.log)
    if args.sequence and (args.pulse_us is not None or args.duration is not None):
        raise CommissioningError("use either --sequence or --pulse-us/--duration")
    if args.sequence:
        if args.axis is None or not args.accept_unmeasured_supply:
            raise CommissioningError("sequence requires --axis and --accept-unmeasured-supply")
        return run_sequence(args)
    if args.axis is None:
        raise CommissioningError("explicit --axis is required")
    validate_args(args)
    return run_single(args)


if __name__ == "__main__":
    raise SystemExit(main())
