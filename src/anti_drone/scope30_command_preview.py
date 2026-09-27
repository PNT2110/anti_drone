"""Software-only, normalized pan/tilt command preview for Scope 30.

This module deliberately has no hardware imports or actuator sink.  The
normalized command space is a diagnostic envelope, not a servo calibration.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _clamp(value: float, lower: float = -1.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def frame_center(frame_width: float, frame_height: float) -> tuple[float, float]:
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("frame geometry must be positive")
    return float(frame_width) / 2.0, float(frame_height) / 2.0


def normalized_error(target_center: tuple[float, float], frame_width: float, frame_height: float) -> tuple[float, float]:
    """Return 2*(target-center)/frame-size, bounded only for preview safety."""
    center_x, center_y = frame_center(frame_width, frame_height)
    raw_x = 2.0 * (float(target_center[0]) - center_x) / float(frame_width)
    raw_y = 2.0 * (float(target_center[1]) - center_y) / float(frame_height)
    if not isfinite(raw_x) or not isfinite(raw_y):
        raise ValueError("target center must be finite")
    return _clamp(raw_x), _clamp(raw_y)


@dataclass(frozen=True)
class PreviewEnvelope:
    """Normalized software bounds; no physical units are implied."""

    neutral: float = 0.0
    minimum: float = -1.0
    maximum: float = 1.0
    max_delta_per_frame: float = 0.25

    def __post_init__(self) -> None:
        if not self.minimum < self.neutral < self.maximum:
            raise ValueError("invalid normalized command envelope")
        if self.max_delta_per_frame <= 0:
            raise ValueError("max_delta_per_frame must be positive")


class CommandPreview:
    """Deterministic target-state to normalized-command preview.

    OBSERVED and LOW_ASSOCIATED_INFERRED are TRACKING. PREDICTED is a bounded
    HOLD_PREVIEW. NONE or camera failure returns toward neutral and cannot
    retain an old target command indefinitely.
    """

    def __init__(self, envelope: PreviewEnvelope | None = None):
        self.envelope = envelope or PreviewEnvelope()
        self.previous = {"pan": self.envelope.neutral, "tilt": self.envelope.neutral}
        self.previous_state: str | None = None

    def reset(self) -> None:
        self.previous = {"pan": self.envelope.neutral, "tilt": self.envelope.neutral}
        self.previous_state = None

    def _rate_limit(self, axis: str, desired: float) -> tuple[float, bool]:
        bounded = _clamp(desired, self.envelope.minimum, self.envelope.maximum)
        previous = self.previous[axis]
        delta = bounded - previous
        limited = previous + max(-self.envelope.max_delta_per_frame, min(self.envelope.max_delta_per_frame, delta))
        return float(limited), abs(limited - bounded) > 1e-12

    def preview(self, *, target_state: str, target_center: tuple[float, float] | None, frame_width: int, frame_height: int, camera_failed: bool = False) -> dict:
        if camera_failed:
            state = "SAFE_NO_TARGET"
            target_state = "NONE"
        elif target_state == "PREDICTED":
            state = "HOLD_PREVIEW"
        elif target_state in {"OBSERVED", "HIGH_OBSERVED", "LOW_ASSOCIATED_INFERRED"} and target_center is not None:
            state = "TRACKING"
        else:
            state = "RETURN_NEUTRAL_PREVIEW" if self.previous_state not in {None, "NO_TARGET", "SAFE_NO_TARGET"} else "NO_TARGET"

        if target_center is not None and target_state in {"OBSERVED", "HIGH_OBSERVED", "LOW_ASSOCIATED_INFERRED", "PREDICTED"} and not camera_failed:
            error_x_norm, error_y_norm = normalized_error(target_center, frame_width, frame_height)
        else:
            error_x_norm, error_y_norm = 0.0, 0.0
        raw_pan = error_x_norm if state in {"TRACKING", "HOLD_PREVIEW"} else self.envelope.neutral
        raw_tilt = error_y_norm if state in {"TRACKING", "HOLD_PREVIEW"} else self.envelope.neutral
        pan, pan_limited = self._rate_limit("pan", raw_pan)
        tilt, tilt_limited = self._rate_limit("tilt", raw_tilt)
        if state in {"RETURN_NEUTRAL_PREVIEW", "NO_TARGET", "SAFE_NO_TARGET"} and pan == self.envelope.neutral and tilt == self.envelope.neutral:
            state = "NO_TARGET" if not camera_failed else "SAFE_NO_TARGET"
        self.previous = {"pan": pan, "tilt": tilt}
        self.previous_state = state
        return {
            "mode": "DRY_RUN_ONLY",
            "state": state,
            "target_state": target_state,
            "error_x_norm": float(error_x_norm),
            "error_y_norm": float(error_y_norm),
            "raw_desired_pan": float(raw_pan),
            "raw_desired_tilt": float(raw_tilt),
            "bounded_pan": float(_clamp(raw_pan, self.envelope.minimum, self.envelope.maximum)),
            "bounded_tilt": float(_clamp(raw_tilt, self.envelope.minimum, self.envelope.maximum)),
            "rate_limited_pan": pan,
            "rate_limited_tilt": tilt,
            "rate_limit_activated": bool(pan_limited or tilt_limited),
            "actuator_output_enabled": False,
            "gpio_write": False,
            "pwm_write": False,
            "serial_write": False,
            "servo_write": False,
            "motor_write": False,
        }
