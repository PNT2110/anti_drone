#!/usr/bin/env python3
"""Run the frozen anti_drone detector/tracker with the ported Pi servo path.

This is a command-run integration tool, not an autostart service.  It uses
Halmstad or another explicitly supplied diagnostic video, never the V3 TEST
split.  Without ``--hardware`` it is a dry-run and no GPIO/PWM/serial call is
made.  With ``--hardware`` the caller explicitly opts into the already-tested
Pi direct transport; cleanup always disables the lines.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import signal
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / "src"))

from scope28_pi_runner import FrozenNcnnDetector  # noqa: E402
from anti_drone.camera_safety import CameraFrameWatchdog  # noqa: E402
from anti_drone.servo import (  # noqa: E402
    DirectServoConfig,
    DronePanTiltController,
    DroneServoBridge,
    NullServoTransport,
    PiDirectServoTransport,
    RunnerAlreadyActive,
    ServoCommand,
    SingleDroneSessionIdentity,
    StableTargetLock,
    acquire_runner_lock,
    select_drone_target,
)
from anti_drone.tracking import ByteTrack, ByteTrackConfig, Detection, Track, TrackState  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parse_sequence(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    value = json.loads(path.read_text())
    if isinstance(value, dict):
        value = value.get("frames", value.get("records", []))
    if not isinstance(value, list):
        raise ValueError("sequence manifest must contain a list")
    return value


def main() -> int:
    def stop_cleanly(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_cleanly)
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--hardware", action="store_true", help="explicitly enable Pi GPIO transport")
    parser.add_argument("--show", action="store_true", help="show annotated tracking window")
    parser.add_argument("--windowed", action="store_true", help="do not use fullscreen display")
    parser.add_argument("--camera", type=str, help="live camera device, for example /dev/video0")
    parser.add_argument("--target-point", help="operator-confirmed source-frame target point as X,Y")
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text())
    output = Path(cfg["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    try:
        runner_lock = acquire_runner_lock(output / "anti_drone_tracking.lock")
    except RunnerAlreadyActive as exc:
        raise SystemExit(f"TRACKING_INSTANCE_ALREADY_ACTIVE: {exc}") from exc
    model = Path(cfg["model_dir"])
    if sha256(model / "model.ncnn.param") != cfg["param_sha256"] or sha256(model / "model.ncnn.bin") != cfg["bin_sha256"]:
        raise SystemExit("DETECTOR_ARTIFACT_HASH_FAIL")
    if "test" in str(cfg.get("video", "")).lower() or "v3" in str(cfg.get("video", "")).lower():
        raise SystemExit("TEST_ACCESS_FORBIDDEN")

    live_camera = args.camera is not None
    sequence = None if live_camera else parse_sequence(Path(cfg["sequence_manifest"]))
    if live_camera:
        cap = cv2.VideoCapture(args.camera, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(cfg.get("camera_width", 1280)))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(cfg.get("camera_height", 720)))
        cap.set(cv2.CAP_PROP_FPS, float(cfg.get("camera_fps", 25)))
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    else:
        cap = cv2.VideoCapture(cfg["video"])
    if not cap.isOpened():
        raise SystemExit("USB_CAMERA_OPEN_FAILED" if live_camera else "DIAGNOSTIC_VIDEO_OPEN_FAILED")
    camera_actual = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if live_camera else None,
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if live_camera else None,
        "fps": float(cap.get(cv2.CAP_PROP_FPS)) if live_camera else None,
        "fourcc": int(cap.get(cv2.CAP_PROP_FOURCC)) if live_camera else None,
        "buffer_size": int(cap.get(cv2.CAP_PROP_BUFFERSIZE)) if live_camera else None,
    }
    window_name = "anti-drone servo tracking"
    display_width = int(cfg.get("display_width", 1920))
    display_height = int(cfg.get("display_height", 1080))
    if args.show:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        if not args.windowed:
            cv2.resizeWindow(window_name, display_width, display_height)
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    mouse_event: list[tuple[str, int, int] | None] = [None]
    if args.show:
        def on_mouse(event, x, y, _flags, _userdata):
            if event == cv2.EVENT_LBUTTONDOWN:
                mouse_event[0] = ("LOCK", int(x), int(y))
            elif event == cv2.EVENT_RBUTTONDOWN:
                mouse_event[0] = ("RESET", int(x), int(y))

        cv2.setMouseCallback(window_name, on_mouse)
    detector = FrozenNcnnDetector(model)
    tracker = ByteTrack(ByteTrackConfig(**cfg["tracker_config"]), mode="motion_adaptive")
    controller = DronePanTiltController()
    transport = PiDirectServoTransport(DirectServoConfig()) if args.hardware else NullServoTransport()
    bridge = DroneServoBridge(controller=controller, transport=transport, identity=SingleDroneSessionIdentity(public_id=1))
    target_lock = StableTargetLock()
    camera_watchdog = CameraFrameWatchdog(max_consecutive_black_frames=3)
    selection_anchor: tuple[float, float] | None = None
    if args.target_point:
        try:
            point_values = [float(value.strip()) for value in args.target_point.split(",")]
        except ValueError as exc:
            raise SystemExit("TARGET_POINT_MUST_BE_X_COMMA_Y") from exc
        if len(point_values) != 2 or not all(np.isfinite(value) and value >= 0 for value in point_values):
            raise SystemExit("TARGET_POINT_MUST_BE_X_COMMA_Y")
        selection_anchor = (point_values[0], point_values[1])
    ids: set[int] = set()
    logical_ids: set[int] = set()
    contained_duplicates_suppressed = 0
    single_drone_candidates_suppressed = 0
    processed_count = 0
    state_counts = {"OBSERVED": 0, "PREDICTED_BLOCKED": 0, "NO_TARGET": 0}
    started = time.monotonic()
    fps_timestamps: deque[float] = deque(maxlen=60)
    displayed_fps = 0.0
    snapshot_interval = max(0.25, float(cfg.get("snapshot_interval_seconds", 1.0)))
    last_latest_snapshot = started - snapshot_interval
    last_detection_snapshot = started - snapshot_interval
    timing_samples = {name: [] for name in ("capture_ms", "preprocess_ms", "inference_ms", "postprocess_ms", "tracker_ms", "target_ms", "pipeline_ms")}
    stopped_by_user = False
    log_handle = (output / "target_state.jsonl").open("w", encoding="utf-8")
    try:
        if args.hardware:
            # The camera is mounted on a load-bearing TILT axis. Leaving PWM
            # off lets the mount sag; later target acquisition then causes a
            # large re-arm jump and motion blur. Hold the commissioned pose
            # from startup and only change it from verified observations.
            transport.arm_pose(ServoCommand(controller.pan.center, controller.tilt.center))
        index = 0
        while True:
            if sequence is not None and index >= len(sequence):
                break
            cycle_start = time.perf_counter()
            capture_start = cycle_start
            ok, frame = cap.read()
            capture_ms = (time.perf_counter() - capture_start) * 1000.0
            if not ok:
                raise RuntimeError("USB camera read failed" if live_camera else f"diagnostic video ended at frame index {index}")
            if live_camera and not camera_watchdog.check(frame):
                # Fail closed on an all-zero UVC frame: no inference,
                # tracking, or stale actuator command is allowed.
                if hasattr(transport, "disarm"):
                    transport.disarm()
                tracker.reset()
                controller.reset()
                target_lock.reset()
                time.sleep(0.05)
                continue
            item = sequence[index] if sequence is not None else {}
            frame_id = int(item.get("frame_id", index + 1))
            timestamp = float(item["timestamp"]) if sequence is not None and "timestamp" in item else time.monotonic()
            pending_mouse = mouse_event[0]
            mouse_event[0] = None
            if pending_mouse is not None:
                action, mouse_x, mouse_y = pending_mouse
                if action == "RESET":
                    selection_anchor = None
                else:
                    if args.windowed:
                        source_x, source_y = float(mouse_x), float(mouse_y)
                    else:
                        view_scale = min(display_width / frame.shape[1], display_height / frame.shape[0])
                        view_width = frame.shape[1] * view_scale
                        view_height = frame.shape[0] * view_scale
                        source_x = (mouse_x - (display_width - view_width) / 2.0) / view_scale
                        source_y = (mouse_y - (display_height - view_height) / 2.0) / view_scale
                    selection_anchor = (
                        max(0.0, min(frame.shape[1] - 1.0, source_x)),
                        max(0.0, min(frame.shape[0] - 1.0, source_y)),
                    )
                tracker.reset()
                controller.reset()
                target_lock.reset()
            streams = detector.infer_dual(frame, preferred_point=selection_anchor)
            if selection_anchor is not None and streams["all"]:
                selected_box = streams["all"][0]["bbox"]
                selection_anchor = (
                    (float(selected_box[0]) + float(selected_box[2])) / 2.0,
                    (float(selected_box[1]) + float(selected_box[3])) / 2.0,
                )
            contained_duplicates_suppressed += int(streams["contract"].get("contained_duplicates_suppressed", 0))
            single_drone_candidates_suppressed += int(streams["contract"].get("single_drone_candidates_suppressed", 0))
            max_raw_confidence = float(np.asarray(streams["raw"])[0, 4].max())
            detections = [
                Detection(np.asarray(row["bbox"], dtype=np.float32), float(row["confidence"]), int(row["class"]))
                for row in streams["all"]
            ]
            tracker_start = time.perf_counter()
            tracks = tracker.update(detections, timestamp=timestamp, frame_id=frame_id, source_frame_id=frame_id)
            tracker_ms = (time.perf_counter() - tracker_start) * 1000.0
            target_start = time.perf_counter()
            control_tracks = tracks
            control_source = "BYTETRACK"
            # A qualifying HIGH observation is actionable immediately. Reuse
            # the safety gate's confidence contract instead of imposing a
            # second, stricter 0.75 threshold that made acquisition appear
            # delayed even though the detector had already accepted a box.
            direct_detection_threshold = (
                target_lock.config.hold_confidence
                if target_lock.locked
                else target_lock.config.acquire_confidence
            )
            direct_row = max(streams["high"], key=lambda row: float(row["confidence"]), default=None)
            if direct_row is not None and float(direct_row["confidence"]) >= direct_detection_threshold:
                direct_box = np.asarray(direct_row["bbox"], dtype=np.float32)
                direct_track = Track(
                    track_id=0,
                    bbox_observed=direct_box,
                    bbox_predicted=direct_box.copy(),
                    confidence=float(direct_row["confidence"]),
                    state=TrackState.CONFIRMED,
                    matched_this_frame=True,
                    last_observed_at=timestamp,
                    observation_count=3,
                    high_confidence_observations=3,
                    hits=3,
                    last_frame=frame_id,
                    last_source_frame=frame_id,
                )
                control_tracks = [direct_track]
                control_source = "STABLE_HIGH_DETECTION"
            elif args.hardware and selection_anchor is None:
                # Autonomous physical motion requires a high-confidence raw
                # observation. ByteTrack alone may retain a false association
                # after the detector confidence has collapsed.
                control_tracks = []
                control_source = "AUTO_CONFIDENCE_BLOCKED"
            lock_candidate = select_drone_target(control_tracks)
            target_lock_state = target_lock.update(
                lock_candidate,
                frame_width=frame.shape[1],
                frame_height=frame.shape[0],
                # The single-drone adapter has already selected one candidate.
                # Competing raw boxes remain logged, while motion stability,
                # confidence, area, and jump gates decide whether auto-control
                # may arm.  A click is an optional override, not a requirement.
                competing_candidates=0,
                confirmed_by_user=selection_anchor is not None,
            )
            result = bridge.update(
                control_tracks,
                frame_width=frame.shape[1],
                frame_height=frame.shape[0],
                timestamp=timestamp,
                actuation_allowed=bool(target_lock_state["actuation_allowed"]),
            )
            target_ms = (time.perf_counter() - target_start) * 1000.0
            ids.update(int(track.track_id) for track in tracks)
            if result["target_id"] is not None:
                logical_ids.add(int(result["target_id"]))
            command = result["command"]
            fps_timestamps.append(time.monotonic())
            if len(fps_timestamps) > 1:
                displayed_fps = (len(fps_timestamps) - 1) / max(fps_timestamps[-1] - fps_timestamps[0], 1e-9)
            display = None
            if args.show:
                display = frame.copy()
                visible_tracks = [
                    track
                    for track in control_tracks
                    if track.is_observed and result["tracker_target_id"] == int(track.track_id)
                ]
                for track in visible_tracks:
                    x1, y1, x2, y2 = [int(round(value)) for value in track.box]
                    color = (0, 0, 255) if target_lock_state["actuation_allowed"] else (0, 210, 255)
                    cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                    label = "DRONE AUTO" if target_lock_state["actuation_allowed"] else "ACQUIRING DRONE"
                    cv2.putText(display, f"{label} ID {result['target_id']} {track.confidence:.2f}", (x1, max(28, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
                if not visible_tracks:
                    for detection in streams["high"]:
                        x1, y1, x2, y2 = [int(round(value)) for value in detection["bbox"]]
                        color = (0, 210, 255)
                        cv2.rectangle(display, (x1, y1), (x2, y2), color, 1)
                        cv2.putText(display, f"DETECTING {detection['confidence']:.2f}", (x1, max(28, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.50, color, 1, cv2.LINE_AA)
                center = (frame.shape[1] // 2, frame.shape[0] // 2)
                cv2.drawMarker(display, center, (255, 0, 255), cv2.MARKER_CROSS, 24, 1)
                if result["target_center"] is not None:
                    target_center = tuple(int(round(value)) for value in result["target_center"])
                    cv2.drawMarker(display, target_center, (0, 255, 255), cv2.MARKER_CROSS, 20, 2)
                    cv2.line(display, center, target_center, (255, 180, 0), 1)
                overlay = display.copy()
                cv2.rectangle(overlay, (6, 6), (620, 166), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.62, display, 0.38, 0.0, display)
                lines = [
                    f"anti-drone | {'LIVE USB CAMERA' if live_camera else f'frame {frame_id}/{len(sequence)}'}",
                    f"FPS={displayed_fps:4.1f}  state={result['state']} target={result['target_id']}",
                    f"raw={max_raw_confidence:.3f} HIGH={len(streams['high'])} LOW={len(streams['low'])} DROP={streams['contract'].get('contained_duplicates_suppressed', 0) + streams['contract'].get('single_drone_candidates_suppressed', 0)}",
                    f"NCNN={streams['timing']['inference_ms']:.1f}ms TRACK={tracker_ms:.1f}ms",
                    f"PAN={command['pan']:.1f}  TILT={command['tilt']:.1f}  {'HARDWARE' if args.hardware else 'DRY RUN'}",
                    f"VEL P/T={result.get('pan_velocity_deg_s', 0.0):+.2f}/{result.get('tilt_velocity_deg_s', 0.0):+.2f} deg/s",
                    f"SERVO={'TRACK' if target_lock_state['actuation_allowed'] else ('HOLD' if result['transport_armed'] else 'OFF')} {target_lock_state['reason']}",
                    "AUTO TARGET LOCK | LEFT CLICK OVERRIDE | RIGHT CLICK/R RESET",
                ]
                for line_index, line in enumerate(lines):
                    cv2.putText(display, line, (12, 26 + line_index * 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
                screen_display = display
                if not args.windowed:
                    # OpenCV's fullscreen window does not reliably scale image
                    # content on the Pi Wayland/XWayland stack.  Build the
                    # fullscreen canvas explicitly so the camera fills the
                    # display while preserving its aspect ratio.  This is a
                    # presentation-only copy; detector/tracker coordinates
                    # remain in the original source-frame space above.
                    scale = min(display_width / display.shape[1], display_height / display.shape[0])
                    scaled_width = max(1, int(round(display.shape[1] * scale)))
                    scaled_height = max(1, int(round(display.shape[0] * scale)))
                    scaled = cv2.resize(display, (scaled_width, scaled_height), interpolation=cv2.INTER_LINEAR)
                    screen_display = np.zeros((display_height, display_width, 3), dtype=np.uint8)
                    offset_x = (display_width - scaled_width) // 2
                    offset_y = (display_height - scaled_height) // 2
                    screen_display[offset_y : offset_y + scaled_height, offset_x : offset_x + scaled_width] = scaled
                cv2.imshow(window_name, screen_display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key == ord("r"):
                    mouse_event[0] = ("RESET", 0, 0)
            pipeline_ms = (time.perf_counter() - cycle_start) * 1000.0
            frame_timing = {
                "capture_ms": capture_ms,
                "preprocess_ms": streams["timing"]["preprocess_ms"],
                "inference_ms": streams["timing"]["inference_ms"],
                "postprocess_ms": streams["timing"]["postprocess_ms"],
                "tracker_ms": tracker_ms,
                "target_ms": target_ms,
                "pipeline_ms": pipeline_ms,
            }
            for name, value in frame_timing.items():
                timing_samples[name].append(float(value))
            row = {
                "frame_id": frame_id,
                "timestamp": timestamp,
                "max_raw_confidence": max_raw_confidence,
                "high_count": len(streams["high"]),
                "low_count": len(streams["low"]),
                "detection_count": len(detections),
                "contained_duplicates_suppressed": streams["contract"].get("contained_duplicates_suppressed", 0),
                "single_drone_candidates_suppressed": streams["contract"].get("single_drone_candidates_suppressed", 0),
                "track_ids": sorted(int(track.track_id) for track in tracks),
                "target_id": result["target_id"],
                "tracker_target_id": result["tracker_target_id"],
                "identity_mode": result["identity_mode"],
                "tracker_id_changes": result["tracker_id_changes"],
                "target_state": result["state"],
                "target_center": result["target_center"],
                "error_x_norm": result["error_x_norm"],
                "error_y_norm": result["error_y_norm"],
                "command": command,
                "controller": {
                    "pan_velocity_deg_s": result.get("pan_velocity_deg_s", 0.0),
                    "tilt_velocity_deg_s": result.get("tilt_velocity_deg_s", 0.0),
                    "pan_deadband": result.get("pan_deadband"),
                    "tilt_deadband": result.get("tilt_deadband"),
                    "dt": result.get("dt"),
                    "profile": "MEDIAN3_ADAPTIVE_P_ACCEL_LIMITED",
                },
                "control_source": control_source,
                "transport_armed": result["transport_armed"],
                "blocked_frames": result["blocked_frames"],
                "target_lock": target_lock_state,
                "manual_selection_anchor": list(selection_anchor) if selection_anchor is not None else None,
                "display_fps": displayed_fps,
                "timing": frame_timing,
                "hardware_requested": bool(args.hardware),
            }
            log_handle.write(json.dumps(row, separators=(",", ":")) + "\n")
            processed_count += 1
            state_counts[result["state"]] = state_counts.get(result["state"], 0) + 1
            if live_camera and processed_count % 10 == 0:
                log_handle.flush()
                (output / "live_state.json").write_text(json.dumps(row, indent=2) + "\n")
            snapshot_now = time.monotonic()
            if live_camera and snapshot_now - last_latest_snapshot >= snapshot_interval:
                cv2.imwrite(str(output / "latest_raw.jpg"), frame)
                cv2.imwrite(str(output / "latest_annotated.jpg"), display if display is not None else frame)
                last_latest_snapshot = snapshot_now
            if live_camera and (streams["high"] or streams["low"]) and snapshot_now - last_detection_snapshot >= snapshot_interval:
                cv2.imwrite(str(output / "last_detection_raw.jpg"), frame)
                cv2.imwrite(str(output / "last_detection_annotated.jpg"), display if display is not None else frame)
                (output / "last_detection_state.json").write_text(json.dumps(row, indent=2) + "\n")
                last_detection_snapshot = snapshot_now
            index += 1
    except KeyboardInterrupt:
        stopped_by_user = True
    finally:
        log_handle.flush()
        log_handle.close()
        cap.release()
        bridge.close()
        if args.show:
            cv2.destroyAllWindows()
        runner_lock.close()

    elapsed = max(time.monotonic() - started, 1e-9)
    def timing_stats(values: list[float]) -> dict:
        if not values:
            return {"mean": None, "p50": None, "p95": None}
        ordered = sorted(values)
        at = lambda ratio: ordered[min(len(ordered) - 1, int((len(ordered) - 1) * ratio))]
        return {"mean": sum(values) / len(values), "p50": at(0.50), "p95": at(0.95)}

    summary = {
        "status": "PI_SERVO_TRACKING_STOPPED_BY_USER" if stopped_by_user else "PI_SERVO_TRACKING_COMPLETE",
        "mode": "HARDWARE" if args.hardware else "DRY_RUN",
        "input": {"type": "USB_CAMERA" if live_camera else "DIAGNOSTIC_VIDEO", "source": args.camera if live_camera else cfg["video"]},
        "camera_actual": camera_actual,
        "frames_processed": processed_count,
        "track_ids_created": sorted(ids),
        "logical_target_ids": sorted(logical_ids),
        "identity_mode": "SINGLE_DRONE_SESSION",
        "contained_duplicates_suppressed": contained_duplicates_suppressed,
        "single_drone_candidates_suppressed": single_drone_candidates_suppressed,
        "observed_frames": state_counts["OBSERVED"],
        "observed_blocked_frames": state_counts.get("OBSERVED_BLOCKED", 0),
        "predicted_blocked_frames": state_counts["PREDICTED_BLOCKED"],
        "no_target_frames": state_counts["NO_TARGET"],
        "effective_fps": processed_count / elapsed,
        "timing_ms": {name: timing_stats(values) for name, values in timing_samples.items()},
        "display": {"fullscreen": bool(args.show and not args.windowed), "fps_overlay": bool(args.show)},
        "detector": {"backend": "NCNN", "precision": "FP32", "param_sha256": cfg["param_sha256"], "bin_sha256": cfg["bin_sha256"], "confidence": 0.25, "nms_iou": 0.70},
        "tracker_profile": "bytetrack_motion_adaptive",
        "servo_mapping": {
            "pan_gpio": 12,
            "tilt_gpio": 13,
            "pan_center": 90.0,
            "tilt_center": 120.0,
            "pan_center_pulse_us": 1450,
            "tilt_center_pulse_us": 2300,
            "tilt_safe_pulse_us": [2100, 2350],
        },
        "physical_output_enabled": bool(args.hardware),
        "test_accessed": False,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
