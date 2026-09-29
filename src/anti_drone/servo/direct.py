"""Explicit Raspberry Pi GPIO transport ported from the working Pi5 rig.

Importing this module is safe.  GPIO is claimed only when
``PiDirectServoTransport`` is instantiated, which must be an explicit caller
choice.  The transport uses the observed anti_drone mapping PAN=BCM12 and
TILT=BCM13 and leaves both lines low/input on cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from .controller import AxisConfig, ServoCommand


def pulse_for_angle(angle: float, axis: AxisConfig, min_pulse_us: int = 500, max_pulse_us: int = 2400) -> int:
    if min_pulse_us <= 0 or max_pulse_us <= min_pulse_us:
        raise ValueError("invalid pulse range")
    bounded = max(axis.minimum, min(axis.maximum, float(angle)))
    # Axis limits and pulse limits are a calibrated pair.  This keeps logical
    # angles useful to the controller without pretending the horn was mounted
    # at the generic 0..180-degree orientation.  In particular, the installed
    # upper axis was camera-verified at 120 -> 2300 us, not 1767 us.
    normalized = (bounded - axis.minimum) / (axis.maximum - axis.minimum)
    if axis.invert:
        normalized = 1.0 - normalized
    return int(round(min_pulse_us + normalized * (max_pulse_us - min_pulse_us)))


@dataclass(frozen=True)
class DirectServoConfig:
    pan_gpio: int = 12
    tilt_gpio: int = 13
    gpio_chip: int | None = None
    frequency_hz: int = 50
    min_pulse_us: int = 500
    max_pulse_us: int = 2400
    tilt_min_pulse_us: int = 2100
    tilt_max_pulse_us: int = 2350
    pan_pulse_offset_us: int = 0
    tilt_pulse_offset_us: int = 10_000
    second_axis_arm_delay_s: float = 0.15
    # Suppress PWM updates smaller than this to prevent servo micro-jitter
    # from detector bbox noise. 8µs ≈ 0.5° on a typical 500-2400µs servo.
    pulse_deadband_us: int = 8
    pan: AxisConfig = AxisConfig(20.0, 160.0, 90.0)
    tilt: AxisConfig = AxisConfig(80.0, 130.0, 120.0)


class NullServoTransport:
    """In-memory transport for dry-run integration and tests."""

    def __init__(self) -> None:
        self.commands: list[ServoCommand] = []
        self.closed = False

    def send(self, command: ServoCommand) -> None:
        if self.closed:
            raise RuntimeError("transport is closed")
        self.commands.append(command)

    def arm_pose(self, command: ServoCommand) -> None:
        self.send(command)

    def close(self) -> None:
        self.closed = True

    def disarm(self) -> None:
        return

    @property
    def armed(self) -> bool:
        return False


class PiDirectServoTransport:
    """Bounded 50 Hz servo transport using lgpio's timed waveform engine.

    Pulse scheduling stays inside lgpio instead of a Python sleep/write loop.
    That keeps NCNN inference and GUI work from modulating servo pulse width.
    """

    def __init__(self, config: DirectServoConfig | None = None, *, lgpio_module=None, monotonic=None, sleeper=None) -> None:
        self.config = config or DirectServoConfig()
        if self.config.frequency_hz <= 0:
            raise ValueError("frequency_hz must be positive")
        self._lgpio = lgpio_module
        self._monotonic = monotonic or time.monotonic
        self._sleep = sleeper or time.sleep
        if self._lgpio is None:
            import lgpio  # type: ignore

            self._lgpio = lgpio
        self._closed = False
        self._armed = False
        self._pan_armed = False
        self._arm_started_at: float | None = None
        self._pending_pan_pulse_us: int | None = None
        self._pan_pulse_us = pulse_for_angle(self.config.pan.center, self.config.pan, self.config.min_pulse_us, self.config.max_pulse_us)
        self._tilt_pulse_us = pulse_for_angle(
            self.config.tilt.center,
            self.config.tilt,
            self.config.tilt_min_pulse_us,
            self.config.tilt_max_pulse_us,
        )
        self._tx_servo = getattr(self._lgpio, "tx_servo", None)
        if not callable(self._tx_servo):
            raise RuntimeError("lgpio.tx_servo is required for stable servo timing")
        
        chip = self.config.gpio_chip
        if chip is None:
            import os
            chip = 4 if os.path.exists("/dev/gpiochip4") else 0
        self._handle = self._lgpio.gpiochip_open(chip)
        claimed: list[int] = []
        try:
            self._lgpio.gpio_claim_output(self._handle, self.config.pan_gpio, 0)
            claimed.append(self.config.pan_gpio)
            self._lgpio.gpio_claim_output(self._handle, self.config.tilt_gpio, 0)
            claimed.append(self.config.tilt_gpio)
        except Exception:
            for gpio in claimed:
                try:
                    self._lgpio.gpio_free(self._handle, gpio)
                except Exception:
                    pass
            self._lgpio.gpiochip_close(self._handle)
            raise

    def _schedule(self, gpio: int, pulse_us: int, pulse_offset_us: int) -> None:
        result = self._tx_servo(
            self._handle,
            gpio,
            int(pulse_us),
            self.config.frequency_hz,
            int(pulse_offset_us),
        )
        if isinstance(result, int) and result < 0:
            raise RuntimeError(f"lgpio.tx_servo failed for GPIO{gpio}: {result}")

    @property
    def armed(self) -> bool:
        return self._armed and not self._closed

    def send(self, command: ServoCommand) -> None:
        if self._closed:
            raise RuntimeError("transport is closed")
        pan = pulse_for_angle(command.pan, self.config.pan, self.config.min_pulse_us, self.config.max_pulse_us)
        tilt = pulse_for_angle(
            command.tilt,
            self.config.tilt,
            self.config.tilt_min_pulse_us,
            self.config.tilt_max_pulse_us,
        )
        if not self._armed:
            # Bring the load-bearing tilt online first. Pan starts on a later
            # control tick, and its pulse is phase-separated from tilt by
            # half of the 20 ms period. This reduces current/ground spikes.
            self._schedule(self.config.tilt_gpio, tilt, self.config.tilt_pulse_offset_us)
            self._tilt_pulse_us = tilt
            self._pending_pan_pulse_us = pan
            self._arm_started_at = self._monotonic()
            self._armed = True
            return
        if tilt != self._tilt_pulse_us:
            if abs(tilt - self._tilt_pulse_us) >= self.config.pulse_deadband_us:
                self._schedule(self.config.tilt_gpio, tilt, self.config.tilt_pulse_offset_us)
                self._tilt_pulse_us = tilt
        if not self._pan_armed:
            self._pending_pan_pulse_us = pan
            if self._monotonic() - float(self._arm_started_at) >= self.config.second_axis_arm_delay_s:
                self._schedule(self.config.pan_gpio, pan, self.config.pan_pulse_offset_us)
                self._pan_pulse_us = pan
                self._pan_armed = True
            return
        if pan != self._pan_pulse_us:
            if abs(pan - self._pan_pulse_us) >= self.config.pulse_deadband_us:
                self._schedule(self.config.pan_gpio, pan, self.config.pan_pulse_offset_us)
                self._pan_pulse_us = pan

    def arm_pose(self, command: ServoCommand) -> None:
        """Hold one commissioned pose, phasing the two axes safely."""

        self.send(command)
        if not self._pan_armed:
            self._sleep(self.config.second_axis_arm_delay_s)
            self.send(command)

    def disarm(self) -> None:
        if self._closed or not self._armed:
            return
        # Raspberry Pi OS documents pulse_width=0 as "off", but this lgpio
        # build rejects tx_servo(..., 0) with ``bad PWM micros``. Releasing a
        # GPIO is the verified cancellation primitive (tx_busy becomes false).
        # Reclaim it LOW so a later observation can re-arm on the same handle.
        for gpio in (self.config.pan_gpio, self.config.tilt_gpio):
            self._lgpio.gpio_free(self._handle, gpio)
            self._lgpio.gpio_claim_output(self._handle, gpio, 0)
        self._armed = False
        self._pan_armed = False
        self._arm_started_at = None
        self._pending_pan_pulse_us = None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for gpio in (self.config.pan_gpio, self.config.tilt_gpio):
            try:
                self._lgpio.gpio_free(self._handle, gpio)
            except Exception:
                pass
            try:
                self._lgpio.gpio_claim_input(self._handle, gpio, getattr(self._lgpio, "SET_PULL_NONE", 0))
                self._lgpio.gpio_free(self._handle, gpio)
            except Exception:
                pass
        self._lgpio.gpiochip_close(self._handle)
