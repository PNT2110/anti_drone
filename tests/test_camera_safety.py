import numpy as np
import pytest

from anti_drone.camera_safety import CameraFrameWatchdog


def test_camera_watchdog_accepts_real_pixels_and_resets_black_count():
    watchdog = CameraFrameWatchdog(max_consecutive_black_frames=3)
    black = np.zeros((4, 4, 3), dtype=np.uint8)
    real = black.copy()
    real[1, 1] = (1, 2, 3)
    assert watchdog.check(black) is False
    assert watchdog.check(real) is True
    assert watchdog.consecutive_black_frames == 0


def test_camera_watchdog_fails_closed_after_three_black_frames():
    watchdog = CameraFrameWatchdog(max_consecutive_black_frames=3)
    black = np.zeros((4, 4, 3), dtype=np.uint8)
    assert watchdog.check(black) is False
    assert watchdog.check(black) is False
    with pytest.raises(RuntimeError, match="USB_CAMERA_BLACK_FRAME_FAILSAFE"):
        watchdog.check(black)


def test_camera_watchdog_rejects_empty_frame():
    watchdog = CameraFrameWatchdog()
    with pytest.raises(RuntimeError, match="USB_CAMERA_EMPTY_FRAME_FAILSAFE"):
        watchdog.check(np.empty((0, 0, 3), dtype=np.uint8))
