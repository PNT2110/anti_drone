"""Drone-track to pan/tilt command adapter.

This is the anti_drone port of the proportional controller from the Pi5
tracking project.  It consumes the repository's ``Track`` objects rather than
the source project's person/COCO target type.  Coordinates are source-frame
pixel coordinates, so no second detector decode or NMS stage is introduced.

The default policy refuses to command from predicted-only tracks.  LOW-stream
observations are still valid observations because Scope 28 preserves their
original confidence and ByteTrack marks them as observed when associated.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Iterable

from ..tracking.types import Track, TrackState


@dataclass(frozen=True)
class AxisConfig:
    """Conservative software angle envelope for one axis."""

    minimum: float
    maximum: float
    center: float
    invert: bool = False

    def __post_init__(self) -> None:
        if not self.minimum < self.center < self.maximum:
            raise ValueError("axis requires minimum < center < maximum")


@dataclass(frozen=True)
class ControllerConfig:
    """Acceleration-limited P-only profile for the installed MG90S mount.

    Ki and Kd intentionally remain zero.  A three-sample median, adaptive
    error filter, hysteretic deadband, braking taper and time-based slew limit
    provide the useful stability layers from ``SPEC_DRONE_TRACKER.pdf``.

    Tuned for smooth drone tracking on MG90S.  The original bench-test defaults
    (kp=1.25, speed=0.80 deg/s) were too slow to follow a moving drone.
    These values balance responsiveness with smooth, jitter-free motion:
    - Moderate kp (1.80/1.40) prevents P-controller oscillation
    - Wide deadzone (0.05) suppresses micro-corrections when on-target
    - High smoothing (0.82) filters detector bbox noise
    - Moderate speed (6.0/5.0 deg/s) is 7-8x faster than original but
      stays well within MG90S capacity (~600 deg/s unloaded)
    - Gentle acceleration (10.0/8.0) prevents jerky direction changes
    """

    kp_pan: float = 1.50
    kp_tilt: float = 1.20
    deadzone: float = 0.06
    tilt_deadzone_scale: float = 1.8
    deadzone_hysteresis: float = 1.5
    brake_zone: float = 0.22
    max_step: float = 0.25
    max_speed_pan: float = 5.0
    max_speed_tilt: float = 4.0
    max_accel_pan: float = 8.0
    max_accel_tilt: float = 6.0
    smoothing: float = 0.88
    error_smoothing: float = 0.50
    adaptive_filter_threshold: float = 0.22
    nominal_dt: float = 1.0 / 13.0
    max_dt: float = 0.20
    lost_recenter_after: int = 45

    def __post_init__(self) -> None:
        if (
            self.max_step <= 0
            or min(self.max_speed_pan, self.max_speed_tilt, self.max_accel_pan, self.max_accel_tilt) <= 0
            or self.lost_recenter_after < 1
            or self.nominal_dt <= 0
            or self.max_dt < self.nominal_dt
        ):
            raise ValueError("invalid controller limits")
        if not 0 <= self.smoothing < 1 or not 0 <= self.error_smoothing < 1:
            raise ValueError("smoothing values must be in [0, 1)")
        if not 0 <= self.deadzone < self.brake_zone <= 1:
            raise ValueError("invalid deadzone/brake zone")
        if self.tilt_deadzone_scale < 1 or self.deadzone_hysteresis < 1:
            raise ValueError("invalid deadzone scaling")


@dataclass(frozen=True)
class ServoCommand:
    pan: float
    tilt: float


def select_drone_target(
    tracks: Iterable[Track],
    *,
    min_observations: int = 3,
    min_high_confidence_observations: int = 2,
) -> Track | None:
    """Select the strongest active observed drone track.

    The detector is one-class (class 0), and the tracker has already applied
    its frozen HIGH/LOW association contract.  Observed tracks win over
    prediction-only tracks; a prediction is returned only as a diagnostic
    candidate and is never commanded by the controller's default policy.
    """

    mature = [
        track
        for track in tracks
        if track.state == TrackState.CONFIRMED
        and track.observation_count >= min_observations
        and track.high_confidence_observations >= min_high_confidence_observations
    ]
    observed = [track for track in mature if track.is_observed]
    return max(observed or mature, key=lambda track: (float(track.confidence), -int(track.track_id)), default=None)


class DronePanTiltController:
    """Bounded proportional image-error controller for drone tracks."""

    def __init__(
        self,
        pan: AxisConfig | None = None,
        tilt: AxisConfig | None = None,
        config: ControllerConfig | None = None,
    ) -> None:
        self.pan = pan or AxisConfig(20.0, 160.0, 90.0)
        # Installed upper-axis calibration: logical center 120 maps to the
        # camera-verified 2300 us neutral inside the 2100..2350 us envelope.
        self.tilt = tilt or AxisConfig(80.0, 130.0, 120.0)
        self.config = config or ControllerConfig()
        self.reset()

    def reset(self) -> None:
        self._pan = self.pan.center
        self._tilt = self.tilt.center
        self._lost_frames = 0
        self._pan_error: float | None = None
        self._tilt_error: float | None = None
        self._pan_error_window: deque[float] = deque(maxlen=3)
        self._tilt_error_window: deque[float] = deque(maxlen=3)
        self._pan_velocity = 0.0
        self._tilt_velocity = 0.0
        self._pan_deadband = True
        self._tilt_deadband = True
        self._last_timestamp: float | None = None

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, float(value)))

    @staticmethod
    def _filtered(previous: float | None, current: float, weight: float) -> float:
        return current if previous is None else weight * previous + (1.0 - weight) * current

    def _axis_step(
        self,
        current: float,
        error: float,
        kp: float,
        axis: AxisConfig,
        *,
        velocity: float,
        dt: float,
        deadzone: float,
        in_deadband: bool,
        max_speed: float,
        max_accel: float,
    ) -> tuple[float, float, bool]:
        magnitude = abs(error)
        if in_deadband:
            in_deadband = magnitude <= deadzone * self.config.deadzone_hysteresis
        else:
            in_deadband = magnitude <= deadzone
        signed = -error if axis.invert else error
        if in_deadband:
            signed = 0.0
        elif magnitude < self.config.brake_zone:
            signed *= magnitude / self.config.brake_zone

        desired_velocity = self._clamp(kp * signed, -max_speed, max_speed)
        velocity_change = self._clamp(desired_velocity - velocity, -max_accel * dt, max_accel * dt)
        velocity += velocity_change
        step = self._clamp(velocity * dt, -self.config.max_step, self.config.max_step)
        bounded = self._clamp(current + step, axis.minimum, axis.maximum)
        if bounded != current + step:
            velocity = 0.0
        return bounded, velocity, in_deadband

    def _reset_motion_filter(self) -> None:
        self._pan_error = None
        self._tilt_error = None
        self._pan_error_window.clear()
        self._tilt_error_window.clear()
        self._pan_velocity = 0.0
        self._tilt_velocity = 0.0
        self._pan_deadband = True
        self._tilt_deadband = True

    def step(
        self,
        track: Track | None,
        *,
        frame_width: int,
        frame_height: int,
        timestamp: float,
        control_enabled: bool = True,
    ) -> dict:
        """Advance one control step and return an auditable command record."""

        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("frame geometry must be positive")
        timestamp = float(timestamp)
        if not isfinite(timestamp):
            raise ValueError("timestamp must be finite")
        if self._last_timestamp is not None and timestamp < self._last_timestamp:
            raise ValueError("timestamp moved backwards")
        dt = self.config.nominal_dt if self._last_timestamp is None else timestamp - self._last_timestamp
        dt = self._clamp(dt, 1e-3, self.config.max_dt)
        self._last_timestamp = timestamp

        observed = track is not None and track.is_observed
        if observed and not control_enabled:
            box = track.box
            center_x = (float(box[0]) + float(box[2])) / 2.0
            center_y = (float(box[1]) + float(box[3])) / 2.0
            self._lost_frames = 0
            self._reset_motion_filter()
            return {
                "state": "OBSERVED_BLOCKED",
                "target_id": int(track.track_id),
                "target_center": [center_x, center_y],
                "error_x_norm": 2.0 * (center_x - frame_width / 2.0) / frame_width,
                "error_y_norm": 2.0 * (center_y - frame_height / 2.0) / frame_height,
                "command": ServoCommand(self._pan, self._tilt),
                "lost_frames": 0,
                "hardware_allowed": False,
            }
        if not observed:
            self._lost_frames += 1
            self._reset_motion_filter()
            return {
                "state": "PREDICTED_BLOCKED" if track is not None else "NO_TARGET",
                "target_id": int(track.track_id) if track is not None else None,
                "target_center": None,
                "error_x_norm": None,
                "error_y_norm": None,
                "command": ServoCommand(self._pan, self._tilt),
                "lost_frames": self._lost_frames,
                # A predicted box is never commanded.  Keep the last real
                # command on loss instead of changing internal state toward a
                # center that was never physically sent.  The old behavior
                # desynchronized software and servo position, then caused a
                # large jump on reacquisition.
                "hardware_allowed": False,
            }

        box = track.box
        center_x = (float(box[0]) + float(box[2])) / 2.0
        center_y = (float(box[1]) + float(box[3])) / 2.0
        error_x = 2.0 * (center_x - frame_width / 2.0) / frame_width
        error_y = 2.0 * (center_y - frame_height / 2.0) / frame_height
        if not all(isfinite(value) for value in (center_x, center_y, error_x, error_y)):
            raise ValueError("track coordinates must be finite")
        error_x = self._clamp(error_x, -1.0, 1.0)
        error_y = self._clamp(error_y, -1.0, 1.0)
        self._lost_frames = 0
        self._pan_error_window.append(error_x)
        self._tilt_error_window.append(error_y)
        median_x = float(median(self._pan_error_window))
        median_y = float(median(self._tilt_error_window))
        pan_weight = self.config.smoothing if abs(median_x) < self.config.adaptive_filter_threshold else self.config.error_smoothing
        tilt_weight = self.config.smoothing if abs(median_y) < self.config.adaptive_filter_threshold else self.config.error_smoothing
        self._pan_error = self._filtered(self._pan_error, median_x, pan_weight)
        self._tilt_error = self._filtered(self._tilt_error, median_y, tilt_weight)
        self._pan, self._pan_velocity, self._pan_deadband = self._axis_step(
            self._pan,
            self._pan_error,
            self.config.kp_pan,
            self.pan,
            velocity=self._pan_velocity,
            dt=dt,
            deadzone=self.config.deadzone,
            in_deadband=self._pan_deadband,
            max_speed=self.config.max_speed_pan,
            max_accel=self.config.max_accel_pan,
        )
        self._tilt, self._tilt_velocity, self._tilt_deadband = self._axis_step(
            self._tilt,
            self._tilt_error,
            self.config.kp_tilt,
            self.tilt,
            velocity=self._tilt_velocity,
            dt=dt,
            deadzone=self.config.deadzone * self.config.tilt_deadzone_scale,
            in_deadband=self._tilt_deadband,
            max_speed=self.config.max_speed_tilt,
            max_accel=self.config.max_accel_tilt,
        )
        return {
            "state": "OBSERVED",
            "target_id": int(track.track_id),
            "target_center": [center_x, center_y],
            "error_x_norm": self._pan_error,
            "error_y_norm": self._tilt_error,
            "command": ServoCommand(self._pan, self._tilt),
            "pan_velocity_deg_s": self._pan_velocity,
            "tilt_velocity_deg_s": self._tilt_velocity,
            "pan_deadband": self._pan_deadband,
            "tilt_deadband": self._tilt_deadband,
            "dt": dt,
            "lost_frames": 0,
            "hardware_allowed": True,
        }
