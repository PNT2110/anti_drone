"""Fail-closed validation for the live USB camera stream."""

from __future__ import annotations

import numpy as np


class CameraFrameWatchdog:
    """Reject all-zero UVC frames and escalate after a short burst."""

    def __init__(self, max_consecutive_black_frames: int = 3) -> None:
        if max_consecutive_black_frames < 1:
            raise ValueError("max_consecutive_black_frames must be positive")
        self.max_consecutive_black_frames = int(max_consecutive_black_frames)
        self.consecutive_black_frames = 0

    def check(self, frame: np.ndarray) -> bool:
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            raise RuntimeError("USB_CAMERA_EMPTY_FRAME_FAILSAFE")
        if int(frame.max()) == 0:
            self.consecutive_black_frames += 1
            if self.consecutive_black_frames >= self.max_consecutive_black_frames:
                raise RuntimeError("USB_CAMERA_BLACK_FRAME_FAILSAFE")
            return False
        self.consecutive_black_frames = 0
        return True
