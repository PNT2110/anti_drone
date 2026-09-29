"""Runtime target-acquisition guard for physical pan/tilt actuation.

The detector thresholds remain unchanged.  This guard only decides whether a
sequence of already-selected observations is trustworthy enough to move the
physical mount.  It deliberately fails closed when detections compete, jump,
or occupy an implausibly large portion of the camera frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class TargetLockConfig:
    # Reduced from 3 to 2 acquire_frames to cut ~71ms latency at 14 FPS.
    # Confidence lowered from 0.60 to 0.55 for faster lock acquisition while
    # still rejecting low-confidence false positives.
    acquire_frames: int = 2
    acquire_confidence: float = 0.55
    hold_confidence: float = 0.35
    max_acquire_center_jump_norm: float = 0.08
    max_hold_center_jump_norm: float = 0.18
    max_box_area_ratio: float = 0.80
    unsafe_frames_before_unlock: int = 3

    def __post_init__(self) -> None:
        if self.acquire_frames < 1 or self.unsafe_frames_before_unlock < 1:
            raise ValueError("frame counts must be positive")
        if not 0 <= self.hold_confidence <= self.acquire_confidence <= 1:
            raise ValueError("invalid target-lock confidences")
        if not 0 < self.max_acquire_center_jump_norm <= self.max_hold_center_jump_norm:
            raise ValueError("invalid target-lock center gates")
        if not 0 < self.max_box_area_ratio <= 1:
            raise ValueError("invalid target-lock area gate")


class StableTargetLock:
    """Require stable, unambiguous observations before allowing movement."""

    def __init__(self, config: TargetLockConfig | None = None) -> None:
        self.config = config or TargetLockConfig()
        self.reset()

    def reset(self) -> None:
        self.locked = False
        self.stable_frames = 0
        self.unsafe_frames = 0
        self._last_center: tuple[float, float] | None = None

    @staticmethod
    def _geometry(track, frame_width: int, frame_height: int) -> tuple[tuple[float, float], float]:
        x1, y1, x2, y2 = (float(value) for value in track.box)
        center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        area_ratio = max(0.0, x2 - x1) * max(0.0, y2 - y1) / float(frame_width * frame_height)
        return center, area_ratio

    def update(
        self,
        track,
        *,
        frame_width: int,
        frame_height: int,
        competing_candidates: int,
        confirmed_by_user: bool = False,
    ) -> dict:
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("frame geometry must be positive")
        if competing_candidates < 0:
            raise ValueError("competing_candidates cannot be negative")

        reason = "LOCKED"
        safe = track is not None and bool(track.is_observed)
        confidence = float(track.confidence) if track is not None else 0.0
        center = None
        area_ratio = None
        jump_norm = None
        if safe:
            center, area_ratio = self._geometry(track, frame_width, frame_height)
            if self._last_center is not None:
                jump_norm = hypot(center[0] - self._last_center[0], center[1] - self._last_center[1]) / hypot(frame_width, frame_height)

        if not safe:
            reason = "NO_OBSERVED_TARGET"
        elif competing_candidates and not confirmed_by_user:
            safe, reason = False, "COMPETING_CANDIDATES"
        elif area_ratio is not None and area_ratio > (0.90 if confirmed_by_user else self.config.max_box_area_ratio):
            safe, reason = False, "BOX_TOO_LARGE"
        elif confidence < (self.config.hold_confidence if self.locked else self.config.acquire_confidence):
            safe, reason = False, "CONFIDENCE_GATE"
        elif jump_norm is not None and jump_norm > (
            self.config.max_hold_center_jump_norm if self.locked else self.config.max_acquire_center_jump_norm
        ):
            safe, reason = False, "CENTER_JUMP"

        if self.locked:
            if safe:
                self.unsafe_frames = 0
                self._last_center = center
            else:
                self.unsafe_frames += 1
                if self.unsafe_frames >= self.config.unsafe_frames_before_unlock:
                    self.locked = False
                    self.stable_frames = 0
                    self._last_center = None
                    reason = f"UNLOCKED_{reason}"
        elif safe:
            self.stable_frames += 1
            self._last_center = center
            if self.stable_frames >= self.config.acquire_frames:
                self.locked = True
                self.unsafe_frames = 0
                reason = "LOCK_ACQUIRED"
            else:
                reason = "ACQUIRING"
        else:
            self.stable_frames = 0
            self._last_center = None

        return {
            "actuation_allowed": bool(self.locked and safe),
            "locked": self.locked,
            "reason": reason,
            "stable_frames": self.stable_frames,
            "unsafe_frames": self.unsafe_frames,
            "confidence": confidence,
            "box_area_ratio": area_ratio,
            "center_jump_norm": jump_norm,
            "competing_candidates": int(competing_candidates),
            "confirmed_by_user": bool(confirmed_by_user),
        }
