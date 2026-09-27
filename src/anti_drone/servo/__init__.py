"""Explicit pan/tilt integration for the frozen drone tracking pipeline.

The package is deliberately opt-in: importing it never touches GPIO, PWM, or
serial hardware.  A hardware transport is created only by the caller.
"""

from .controller import (
    AxisConfig,
    ControllerConfig,
    DronePanTiltController,
    ServoCommand,
    select_drone_target,
)
from .direct import DirectServoConfig, NullServoTransport, PiDirectServoTransport, pulse_for_angle
from .safety import StableTargetLock, TargetLockConfig
from .bridge import DroneServoBridge
from .identity import SingleDroneSessionIdentity
from .instance_lock import RunnerAlreadyActive, acquire_runner_lock

__all__ = [
    "AxisConfig",
    "ControllerConfig",
    "DronePanTiltController",
    "DroneServoBridge",
    "SingleDroneSessionIdentity",
    "RunnerAlreadyActive",
    "DirectServoConfig",
    "NullServoTransport",
    "PiDirectServoTransport",
    "ServoCommand",
    "pulse_for_angle",
    "StableTargetLock",
    "TargetLockConfig",
    "select_drone_target",
    "acquire_runner_lock",
]
