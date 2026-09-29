"""Process-level lock for the camera/GPIO tracking runner.

The lock is intentionally independent of GPIO.  Acquiring it never touches
hardware; it only prevents a second runner from opening the same camera and
servo transport concurrently.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TextIO


class RunnerAlreadyActive(RuntimeError):
    """Raised when another tracking runner owns the lock."""


def acquire_runner_lock(path: Path) -> TextIO:
    """Acquire a non-blocking advisory lock and return its open handle.

    The caller must keep the returned handle open for the lifetime of the
    process and close it during cleanup.  The small text file may remain on
    disk; ownership is represented by ``flock`` on POSIX or ``msvcrt.locking``
    on Windows, not by file existence.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        import msvcrt
        # On Windows, open the file for read+write. Write a single sentinel
        # byte so msvcrt.locking can lock exactly that byte range. The second
        # caller will fail to lock the same byte and raise RunnerAlreadyActive.
        path.touch(exist_ok=True)
        # Open in binary mode for msvcrt compatibility, wrap in TextIO later
        fd = os.open(str(path), os.O_RDWR)
        try:
            # Ensure file has at least 1 byte for locking
            os.write(fd, b" ")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except (IOError, OSError):
            os.close(fd)
            raise RunnerAlreadyActive(
                f"tracking runner already active (owner PID unknown)"
            )
        # Lock acquired — write PID
        os.lseek(fd, 0, os.SEEK_SET)
        pid_bytes = f"{os.getpid()}\n".encode()
        os.write(fd, pid_bytes)
        os.fsync(fd)
        # Wrap fd in a TextIO handle for API compatibility
        handle = os.fdopen(fd, "r+", encoding="utf-8")
        return handle
    else:
        import fcntl
        handle = path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.seek(0)
            owner = handle.read().strip() or "unknown"
            handle.close()
            raise RunnerAlreadyActive(
                f"tracking runner already active (owner PID {owner})"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        return handle
