"""Small bridge from anti_drone tracks to the ported pan/tilt algorithm."""

from __future__ import annotations

from .controller import DronePanTiltController, ServoCommand, select_drone_target
from .direct import NullServoTransport


class DroneServoBridge:
    """Target-selection and command bridge; hardware is opt-in."""

    def __init__(
        self,
        controller: DronePanTiltController | None = None,
        transport=None,
        identity=None,
        *,
        disarm_after_blocked_frames: int | None = None,
    ) -> None:
        if disarm_after_blocked_frames is not None and disarm_after_blocked_frames < 1:
            raise ValueError("disarm_after_blocked_frames must be positive")
        self.controller = controller or DronePanTiltController()
        self.transport = transport or NullServoTransport()
        self.identity = identity
        self.disarm_after_blocked_frames = (
            int(disarm_after_blocked_frames) if disarm_after_blocked_frames is not None else None
        )
        self._blocked_frames = 0

    def update(self, tracks, *, frame_width: int, frame_height: int, timestamp: float, actuation_allowed: bool = True) -> dict:
        target = select_drone_target(tracks)
        result = self.controller.step(
            target,
            frame_width=frame_width,
            frame_height=frame_height,
            timestamp=timestamp,
            control_enabled=actuation_allowed,
        )
        command = result["command"]
        if result["hardware_allowed"] and actuation_allowed:
            self._blocked_frames = 0
            self.transport.send(command)
        else:
            # Keep the last pulse during an observation gap without sending
            # any new position. Releasing the load-bearing TILT axis made the
            # camera sag substantially; reacquiring torque then moved the
            # whole camera and blurred the next frames. The runner still
            # disarms immediately on camera failure and during final cleanup.
            self._blocked_frames += 1
        if (
            self.disarm_after_blocked_frames is not None
            and self._blocked_frames >= self.disarm_after_blocked_frames
            and hasattr(self.transport, "disarm")
        ):
            self.transport.disarm()
        result = {
            **result,
            "command": {"pan": command.pan, "tilt": command.tilt},
            "transport_armed": bool(getattr(self.transport, "armed", False)),
            "blocked_frames": self._blocked_frames,
        }
        return self.identity.apply(result) if self.identity is not None else result

    def close(self) -> None:
        self.transport.close()
