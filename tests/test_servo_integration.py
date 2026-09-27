"""Unit guards for the ported drone pan/tilt integration."""

from __future__ import annotations

import types

import numpy as np

from anti_drone.servo import (
    AxisConfig,
    ControllerConfig,
    DirectServoConfig,
    DronePanTiltController,
    DroneServoBridge,
    NullServoTransport,
    PiDirectServoTransport,
    SingleDroneSessionIdentity,
    StableTargetLock,
    TargetLockConfig,
    pulse_for_angle,
    RunnerAlreadyActive,
    acquire_runner_lock,
)
from anti_drone.tracking.types import Track, TrackState


def observed_track(track_id: int = 1, box=(280.0, 210.0, 360.0, 270.0)) -> Track:
    return Track(
        track_id=track_id,
        bbox_observed=np.asarray(box, dtype=np.float32),
        bbox_predicted=np.asarray(box, dtype=np.float32),
        confidence=0.8,
        state=TrackState.CONFIRMED,
        matched_this_frame=True,
        observation_count=3,
        high_confidence_observations=3,
    )


def predicted_track(track_id: int = 1) -> Track:
    box = np.asarray((280.0, 210.0, 360.0, 270.0), dtype=np.float32)
    return Track(
        track_id,
        None,
        box,
        0.8,
        TrackState.CONFIRMED,
        False,
        observation_count=3,
        high_confidence_observations=3,
    )


def test_anti_drone_defaults_use_camera_calibrated_pi_mapping_and_centers():
    config = DirectServoConfig()
    assert config.pan_gpio == 12
    assert config.tilt_gpio == 13
    assert config.pan.center == 90.0
    assert config.tilt.center == 120.0
    assert pulse_for_angle(90, config.pan) == 1450
    assert pulse_for_angle(120, config.tilt, config.tilt_min_pulse_us, config.tilt_max_pulse_us) == 2300
    assert pulse_for_angle(80, config.tilt, config.tilt_min_pulse_us, config.tilt_max_pulse_us) == 2100
    assert pulse_for_angle(130, config.tilt, config.tilt_min_pulse_us, config.tilt_max_pulse_us) == 2350


def test_controller_consumes_source_pixel_drone_track_and_is_bounded():
    controller = DronePanTiltController()
    result = controller.step(observed_track(box=(560, 420, 640, 480)), frame_width=640, frame_height=480, timestamp=1.0)
    assert result["state"] == "OBSERVED"
    assert result["target_id"] == 1
    assert result["target_center"] == [600.0, 450.0]
    assert 20.0 <= result["command"].pan <= 160.0
    assert 80.0 <= result["command"].tilt <= 130.0


def test_default_controller_uses_gentle_live_servo_profile():
    config = ControllerConfig()
    assert config.kp_pan == 1.25
    assert config.kp_tilt == 1.25
    assert config.deadzone == 0.04
    assert config.tilt_deadzone_scale == 2.0
    assert config.deadzone_hysteresis == 1.5
    assert config.max_speed_pan == 0.80
    assert config.max_speed_tilt == 0.60
    assert config.max_accel_pan == 1.50
    assert config.max_accel_tilt == 1.00
    assert config.max_step == 0.25
    assert config.smoothing == 0.85
    assert config.error_smoothing == 0.50

    controller = DronePanTiltController(config=config)
    first = controller.step(
        observed_track(box=(1120, 560, 1270, 710)),
        frame_width=1280,
        frame_height=720,
        timestamp=1.0,
    )
    # The first update is acceleration-limited and substantially below the
    # absolute per-command safety cap.
    assert abs(first["command"].pan - 90.0) <= 0.051
    assert abs(first["command"].tilt - 120.0) <= 0.051
    assert abs(first["pan_velocity_deg_s"]) <= config.max_accel_pan * config.nominal_dt + 1e-9
    assert abs(first["tilt_velocity_deg_s"]) <= config.max_accel_tilt * config.nominal_dt + 1e-9


def test_three_sample_median_prevents_single_bbox_jump_from_reversing_pan():
    controller = DronePanTiltController()
    right = observed_track(box=(920, 260, 1000, 340))
    left_outlier = observed_track(box=(0, 260, 80, 340))
    first = controller.step(right, frame_width=1280, frame_height=720, timestamp=1.0)
    jumped = controller.step(left_outlier, frame_width=1280, frame_height=720, timestamp=1.1)
    recovered = controller.step(right, frame_width=1280, frame_height=720, timestamp=1.2)

    assert jumped["error_x_norm"] > 0
    assert recovered["error_x_norm"] > 0
    assert jumped["command"].pan >= first["command"].pan
    assert recovered["command"].pan >= jumped["command"].pan


def test_runner_lock_rejects_second_instance_and_releases_on_close(tmp_path):
    path = tmp_path / "anti_drone_tracking.lock"
    first = acquire_runner_lock(path)
    try:
        assert path.read_text().strip().isdigit()
        try:
            acquire_runner_lock(path)
        except RunnerAlreadyActive as exc:
            assert "owner PID" in str(exc)
        else:
            raise AssertionError("second runner unexpectedly acquired the lock")
    finally:
        first.close()

    second = acquire_runner_lock(path)
    second.close()


def test_one_frame_false_positive_is_not_selected_for_display_or_actuation():
    transport = NullServoTransport()
    tentative = observed_track()
    tentative.state = TrackState.TENTATIVE
    tentative.observation_count = 1
    tentative.high_confidence_observations = 1
    bridge = DroneServoBridge(transport=transport)
    result = bridge.update([tentative], frame_width=640, frame_height=480, timestamp=1.0)
    assert result["state"] == "NO_TARGET"
    assert result["target_id"] is None
    assert transport.commands == []
    bridge.close()


def test_predicted_track_is_never_sent_to_transport():
    transport = NullServoTransport()
    bridge = DroneServoBridge(transport=transport)
    result = bridge.update([predicted_track()], frame_width=640, frame_height=480, timestamp=1.0)
    assert result["state"] == "PREDICTED_BLOCKED"
    assert transport.commands == []
    bridge.close()


def test_short_detection_gap_holds_last_pulse_then_disarms_without_new_commands():
    class RecordingTransport:
        def __init__(self):
            self.commands = []
            self.disarms = 0

        def send(self, command):
            self.commands.append(command)

        def disarm(self):
            self.disarms += 1

        def close(self):
            return

    transport = RecordingTransport()
    bridge = DroneServoBridge(transport=transport, disarm_after_blocked_frames=3)
    bridge.update([observed_track()], frame_width=640, frame_height=480, timestamp=1.0)
    bridge.update([], frame_width=640, frame_height=480, timestamp=1.1)
    bridge.update([], frame_width=640, frame_height=480, timestamp=1.2)
    assert len(transport.commands) == 1
    assert transport.disarms == 0
    bridge.update([], frame_width=640, frame_height=480, timestamp=1.3)
    assert len(transport.commands) == 1
    assert transport.disarms == 1
    bridge.close()


def test_default_bridge_keeps_last_pose_armed_during_detector_flicker():
    bridge = DroneServoBridge(transport=NullServoTransport())
    assert bridge.disarm_after_blocked_frames is None
    bridge.close()


def test_observed_track_is_sent_to_dry_run_transport_and_loss_recenters_only_after_policy():
    transport = NullServoTransport()
    bridge = DroneServoBridge(transport=transport)
    observed = bridge.update([observed_track(box=(0, 0, 80, 80))], frame_width=640, frame_height=480, timestamp=1.0)
    missing = bridge.update([], frame_width=640, frame_height=480, timestamp=1.1)
    assert observed["state"] == "OBSERVED"
    assert len(transport.commands) == 1
    assert missing["state"] == "NO_TARGET"
    assert len(transport.commands) == 1
    bridge.close()


def test_single_drone_public_id_survives_internal_track_recreation():
    identity = SingleDroneSessionIdentity(public_id=1)
    bridge = DroneServoBridge(transport=NullServoTransport(), identity=identity)
    first = bridge.update([observed_track(track_id=21)], frame_width=640, frame_height=480, timestamp=1.0)
    lost = bridge.update([], frame_width=640, frame_height=480, timestamp=1.1)
    reacquired = bridge.update([observed_track(track_id=44)], frame_width=640, frame_height=480, timestamp=1.2)
    assert first["target_id"] == 1
    assert first["tracker_target_id"] == 21
    assert lost["target_id"] is None
    assert reacquired["target_id"] == 1
    assert reacquired["tracker_target_id"] == 44
    assert reacquired["tracker_id_changes"] == 1
    bridge.close()


def test_long_complete_loss_holds_last_real_command_and_prediction_stays_blocked():
    transport = NullServoTransport()
    controller = DronePanTiltController(config=ControllerConfig(lost_recenter_after=2))
    bridge = DroneServoBridge(controller=controller, transport=transport)
    observed = bridge.update([observed_track(box=(0, 0, 80, 80))], frame_width=640, frame_height=480, timestamp=1.0)
    bridge.update([], frame_width=640, frame_height=480, timestamp=1.1)
    result = bridge.update([], frame_width=640, frame_height=480, timestamp=1.2)
    assert result["hardware_allowed"] is False
    assert result["command"] == observed["command"]
    assert len(transport.commands) == 1
    assert bridge.update([predicted_track()], frame_width=640, frame_height=480, timestamp=1.3)["hardware_allowed"] is False
    bridge.close()


def test_direct_transport_claims_pan12_tilt13_and_cleans_up_without_real_gpio():
    calls = []
    clock = [0.0]
    fake = types.SimpleNamespace(
        SET_PULL_NONE=0,
        gpiochip_open=lambda chip: calls.append(("open", chip)) or 7,
        gpio_claim_output=lambda handle, gpio, level: calls.append(("claim_output", handle, gpio, level)),
        gpio_claim_input=lambda handle, gpio, flags: calls.append(("claim_input", handle, gpio, flags)),
        gpio_write=lambda handle, gpio, level: calls.append(("write", handle, gpio, level)),
        tx_servo=lambda handle, gpio, pulse, frequency, offset=0: calls.append(("tx_servo", handle, gpio, pulse, frequency, offset)) or 0,
        gpio_free=lambda handle, gpio: calls.append(("free", handle, gpio)),
        gpiochip_close=lambda handle: calls.append(("close", handle)),
    )
    driver = PiDirectServoTransport(lgpio_module=fake, monotonic=lambda: clock[0], sleeper=lambda _: None)
    assert driver.armed is False
    driver.send(types.SimpleNamespace(pan=90.0, tilt=120.0))
    assert driver.armed is True
    assert ("tx_servo", 7, 13, 2300, 50, 10000) in calls
    assert not any(call[:3] == ("tx_servo", 7, 12) and call[3] > 0 for call in calls)
    clock[0] = 0.2
    driver.send(types.SimpleNamespace(pan=90.0, tilt=120.0))
    before_disarm = len(calls)
    driver.disarm()
    assert driver.armed is False
    disarm_calls = calls[before_disarm:]
    assert ("free", 7, 12) in disarm_calls
    assert ("free", 7, 13) in disarm_calls
    assert ("claim_output", 7, 12, 0) in disarm_calls
    assert ("claim_output", 7, 13, 0) in disarm_calls
    assert not any(call[0] == "tx_servo" and call[3] == 0 for call in disarm_calls)
    driver.close()
    assert ("claim_output", 7, 12, 0) in calls
    assert ("claim_output", 7, 13, 0) in calls
    assert ("tx_servo", 7, 12, 1450, 50, 0) in calls
    assert not any(call[0] == "tx_servo" and call[3] == 0 for call in calls)
    assert ("claim_input", 7, 12, 0) in calls
    assert ("claim_input", 7, 13, 0) in calls
    assert calls[-1] == ("close", 7)


def test_arm_pose_phases_tilt_then_pan_without_position_sweep():
    calls = []
    clock = [0.0]

    def sleep(seconds):
        clock[0] += seconds

    fake = types.SimpleNamespace(
        SET_PULL_NONE=0,
        gpiochip_open=lambda chip: 8,
        gpio_claim_output=lambda handle, gpio, level: calls.append(("claim", gpio, level)),
        gpio_claim_input=lambda handle, gpio, flags: None,
        gpio_free=lambda handle, gpio: None,
        gpiochip_close=lambda handle: None,
        tx_servo=lambda handle, gpio, pulse, frequency, offset=0: calls.append(
            ("servo", gpio, pulse, frequency, offset)
        )
        or 0,
    )
    driver = PiDirectServoTransport(lgpio_module=fake, monotonic=lambda: clock[0], sleeper=sleep)
    driver.arm_pose(types.SimpleNamespace(pan=90.0, tilt=120.0))
    servo_calls = [call for call in calls if call[0] == "servo"]
    assert servo_calls == [
        ("servo", 13, 2300, 50, 10000),
        ("servo", 12, 1450, 50, 0),
    ]
    assert driver.armed is True
    driver.close()


def test_target_lock_rejects_competing_detections_and_controller_does_not_wind_up():
    gate = StableTargetLock(TargetLockConfig(acquire_frames=2))
    track = observed_track(box=(700, 0, 1270, 450))
    blocked = gate.update(track, frame_width=1280, frame_height=720, competing_candidates=1)
    assert blocked["actuation_allowed"] is False
    assert blocked["reason"] == "COMPETING_CANDIDATES"

    controller = DronePanTiltController()
    initial = controller.step(track, frame_width=1280, frame_height=720, timestamp=1.0, control_enabled=False)
    repeated = controller.step(track, frame_width=1280, frame_height=720, timestamp=2.0, control_enabled=False)
    assert initial["state"] == "OBSERVED_BLOCKED"
    assert repeated["command"] == initial["command"]
    assert repeated["command"].pan == 90.0
    assert repeated["command"].tilt == 120.0


def test_target_lock_requires_stability_then_unlocks_on_repeated_jump():
    gate = StableTargetLock(TargetLockConfig(acquire_frames=3, unsafe_frames_before_unlock=2))
    first = observed_track(box=(500, 250, 780, 470))
    assert gate.update(first, frame_width=1280, frame_height=720, competing_candidates=0)["reason"] == "ACQUIRING"
    assert gate.update(first, frame_width=1280, frame_height=720, competing_candidates=0)["actuation_allowed"] is False
    acquired = gate.update(first, frame_width=1280, frame_height=720, competing_candidates=0)
    assert acquired["actuation_allowed"] is True
    jumped = observed_track(box=(0, 0, 200, 160))
    assert gate.update(jumped, frame_width=1280, frame_height=720, competing_candidates=0)["actuation_allowed"] is False
    unlocked = gate.update(jumped, frame_width=1280, frame_height=720, competing_candidates=0)
    assert unlocked["locked"] is False
    assert unlocked["reason"].startswith("UNLOCKED_")


def test_target_lock_rejects_implausibly_large_box():
    gate = StableTargetLock(TargetLockConfig(acquire_frames=1))
    huge = observed_track(box=(0, 0, 1200, 710))
    result = gate.update(huge, frame_width=1280, frame_height=720, competing_candidates=0)
    assert result["actuation_allowed"] is False
    assert result["reason"] == "BOX_TOO_LARGE"


def test_default_target_lock_rejects_two_frame_transient_then_acquires_on_third():
    gate = StableTargetLock()
    updates = [
        gate.update(
            observed_track(box=(500, 250, 780, 470)),
            frame_width=1280,
            frame_height=720,
            competing_candidates=0,
        )
        for _ in range(3)
    ]
    assert gate.config.acquire_frames == 3
    assert updates[0]["actuation_allowed"] is False
    assert updates[1]["actuation_allowed"] is False
    assert updates[2]["actuation_allowed"] is True
    assert updates[2]["reason"] == "LOCK_ACQUIRED"


def test_user_confirmed_target_can_disambiguate_but_still_requires_stability():
    gate = StableTargetLock(TargetLockConfig(acquire_frames=2))
    candidate = observed_track(box=(700, 0, 1270, 450))
    first = gate.update(
        candidate,
        frame_width=1280,
        frame_height=720,
        competing_candidates=2,
        confirmed_by_user=True,
    )
    second = gate.update(
        candidate,
        frame_width=1280,
        frame_height=720,
        competing_candidates=2,
        confirmed_by_user=True,
    )
    assert first["actuation_allowed"] is False
    assert first["reason"] == "ACQUIRING"
    assert second["actuation_allowed"] is True
    assert second["confirmed_by_user"] is True
