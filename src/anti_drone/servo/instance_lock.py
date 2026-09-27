"""Process-level lock for the camera/GPIO tracking runner.

The lock is intentionally independent of GPIO.  Acquiring it never touches
hardware; it only prevents a second runner from opening the same camera and
servo transport concurrently.
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import TextIO


class RunnerAlreadyActive(RuntimeError):
    """Raised when another tracking runner owns the lock."""


def acquire_runner_lock(path: Path) -> TextIO:
    """Acquire a non-blocking advisory lock and return its open handle.

    The caller must keep the returned handle open for the lifetime of the
    process and close it during cleanup.  The small text file may remain on
    disk; ownership is represented by ``flock``, not by file existence.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.seek(0)
        owner = handle.read().strip() or "unknown"
        handle.close()
        raise RunnerAlreadyActive(f"tracking runner already active (owner PID {owner})") from exc
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle
