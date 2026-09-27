#!/usr/bin/env python3
"""Scope 30 physical-webcam target-presence dry-run on Raspberry Pi 5."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / "src"))

from scope21_pi_runner import meminfo, vcgencmd  # noqa: E402
from scope28_pi_runner import FrozenNcnnDetector, association_source, select_target, valid_box  # noqa: E402
from scope29_pi_live import LiveCapture, RingSamples, hardware, rss_kb, stats  # noqa: E402
from anti_drone.scope30_command_preview import CommandPreview, PreviewEnvelope  # noqa: E402
from anti_drone.tracking import ByteTrack, ByteTrackConfig, Detection  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text())
    output = Path(cfg["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    expected_param = cfg["param_sha256"]
    expected_bin = cfg["bin_sha256"]
    hw = hardware()
    if hw["machine"] != "aarch64" or "Raspberry Pi 5 Model B Rev 1.0" not in (hw["model"] or ""):
        raise SystemExit("PI_IDENTITY_FAIL")
    model = Path(cfg["model_dir"])
    if digest(model / "model.ncnn.param") != expected_param or digest(model / "model.ncnn.bin") != expected_bin:
        raise SystemExit("DETECTOR_ARTIFACT_HASH_FAIL")

    capture = LiveCapture(cfg["device"], int(cfg["width"]), int(cfg["height"]), int(cfg["fps"]))
    if not capture.open():
        result = {"status": "CAMERA_OPEN_FAILED", "camera": {"device": cfg["device"]}, "actuator": {"mode": "DRY_RUN_ONLY", "enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0}, "test_accessed": False}
        (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        return 2

    detector = FrozenNcnnDetector(model)
    tracker = ByteTrack(ByteTrackConfig(**cfg["tracker_config"]), mode="motion_adaptive")
    preview = CommandPreview(PreviewEnvelope(**cfg.get("preview_envelope", {})))
    duration = float(cfg["duration_s"])
    capture.start()
    started = time.monotonic()
    deadline = started + duration
    latencies = {key: RingSamples() for key in ("queue_wait_ms", "inference_ms", "postprocess_ms", "tracker_update_ms", "target_selection_ms", "total_processing_ms", "capture_to_result_age_ms")}
    rows = []
    counts = {key: 0 for key in ("high_detection_frames", "low_detection_frames", "low_only_detection_frames", "target_observed_frames", "low_associated_inferred_frames", "prediction_only_frames", "no_target_frames")}
    events = {key: [] for key in ("TRACK_LOST", "TRACK_REACQUIRED", "ID_SWITCH", "TARGET_SWITCH", "TARGET_NULL", "TIMESTAMP_ERROR", "COORDINATE_ERROR", "RATE_LIMIT")}
    track_ids = set()
    previous_timestamp = None
    previous_target_id = None
    previous_target_state = None
    error_x_px, error_y_px, error_x_norm, error_y_norm = [], [], [], []
    command_pan, command_tilt, raw_pan, raw_tilt = [], [], [], []
    neutral_transitions = 0
    log_path = output / "target_state.jsonl"
    with log_path.open("w") as log:
        while time.monotonic() < deadline:
            item = capture.get(timeout=0.25)
            if item is None:
                if capture.error:
                    break
                continue
            timestamp = float(item["capture_timestamp_monotonic"])
            frame = item["frame"]
            frame_h, frame_w = frame.shape[:2]
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                events["TIMESTAMP_ERROR"].append(item["capture_id"])
            previous_timestamp = timestamp
            process_start = time.monotonic()
            streams = detector.infer_dual(frame)
            tracker_start = time.monotonic()
            detections = [Detection(np.asarray(row["bbox"], dtype=np.float32), float(row["confidence"]), int(row["class"])) for row in streams["all"]]
            tracks = tracker.update(detections, timestamp=timestamp, frame_id=int(item["capture_id"]), source_frame_id=int(item["capture_id"]))
            tracker_ms = (time.monotonic() - tracker_start) * 1000.0
            target_start = time.monotonic()
            target = select_target(tracks)
            target_ms = (time.monotonic() - target_start) * 1000.0
            source = association_source(target, streams["high"], streams["low"])
            if target is None:
                target_state = "NONE"
                target_center = None
            elif not target.is_observed:
                target_state = "PREDICTED"
                target_center = [float((target.box[0] + target.box[2]) / 2.0), float((target.box[1] + target.box[3]) / 2.0)]
            elif source == "LOW":
                target_state = "LOW_ASSOCIATED_INFERRED"
                target_center = [float((target.box[0] + target.box[2]) / 2.0), float((target.box[1] + target.box[3]) / 2.0)]
            else:
                target_state = "HIGH_OBSERVED"
                target_center = [float((target.box[0] + target.box[2]) / 2.0), float((target.box[1] + target.box[3]) / 2.0)]
            command = preview.preview(target_state=target_state, target_center=tuple(target_center) if target_center else None, frame_width=frame_w, frame_height=frame_h)
            if target_center:
                ex = target_center[0] - frame_w / 2.0; ey = target_center[1] - frame_h / 2.0
                error_x_px.append(ex); error_y_px.append(ey); error_x_norm.append(command["error_x_norm"]); error_y_norm.append(command["error_y_norm"])
                if source == "HIGH": counts["target_observed_frames"] += 1
                elif source == "LOW": counts["low_associated_inferred_frames"] += 1
                elif target_state == "PREDICTED": counts["prediction_only_frames"] += 1
                else: counts["target_observed_frames"] += 1
            else:
                counts["no_target_frames"] += 1
            if streams["high"]: counts["high_detection_frames"] += 1
            if streams["low"]: counts["low_detection_frames"] += 1
            if not streams["high"] and streams["low"]: counts["low_only_detection_frames"] += 1
            if previous_target_state in {"HIGH_OBSERVED", "LOW_ASSOCIATED_INFERRED"} and target_state == "PREDICTED": events["TRACK_LOST"].append(item["capture_id"])
            if previous_target_state == "PREDICTED" and target_state in {"HIGH_OBSERVED", "LOW_ASSOCIATED_INFERRED"}: events["TRACK_REACQUIRED"].append(item["capture_id"])
            target_id = int(target.track_id) if target is not None else None
            if previous_target_id is not None and target_id is not None and target_id != previous_target_id:
                events["ID_SWITCH"].append(item["capture_id"])
                events["TARGET_SWITCH"].append(item["capture_id"])
            if target_id is None: events["TARGET_NULL"].append(item["capture_id"])
            for track in tracks:
                track_ids.add(int(track.track_id))
                if not valid_box(track.box, frame.shape[:2]): events["COORDINATE_ERROR"].append(item["capture_id"])
            if command["rate_limit_activated"]: events["RATE_LIMIT"].append(item["capture_id"])
            if command["state"] in {"RETURN_NEUTRAL_PREVIEW", "NO_TARGET", "SAFE_NO_TARGET"} and command["rate_limited_pan"] == 0.0 and command["rate_limited_tilt"] == 0.0:
                neutral_transitions += 1
            total_ms = (time.monotonic() - process_start) * 1000.0
            latencies["queue_wait_ms"].append((process_start - timestamp) * 1000.0)
            latencies["inference_ms"].append(float(streams["timing"]["inference_ms"]))
            latencies["postprocess_ms"].append(float(streams["timing"]["postprocess_ms"]))
            latencies["tracker_update_ms"].append(tracker_ms); latencies["target_selection_ms"].append(target_ms); latencies["total_processing_ms"].append(total_ms); latencies["capture_to_result_age_ms"].append((time.monotonic() - timestamp) * 1000.0)
            command_pan.append(command["rate_limited_pan"]); command_tilt.append(command["rate_limited_tilt"]); raw_pan.append(command["raw_desired_pan"]); raw_tilt.append(command["raw_desired_tilt"])
            row = {"frame_id": int(item["capture_id"]), "capture_timestamp_monotonic": timestamp, "source_resolution": [frame_w, frame_h], "high_detections": streams["high"], "low_detections": streams["low"], "track_ids": sorted(int(t.track_id) for t in tracks), "selected_target_id": target_id, "target_bbox": [float(x) for x in target.box] if target is not None else None, "target_center": target_center, "target_state": target_state, "target_association_source": source, "error_x_px": (target_center[0] - frame_w / 2.0) if target_center else None, "error_y_px": (target_center[1] - frame_h / 2.0) if target_center else None, "error_x_norm": command["error_x_norm"], "error_y_norm": command["error_y_norm"], "command_preview": command, "actuator_output_enabled": False, "dry_run": True, "latency_ms": {"inference": streams["timing"]["inference_ms"], "postprocess": streams["timing"]["postprocess_ms"], "tracker_update": tracker_ms, "target_selection": target_ms, "total_processing": total_ms, "capture_to_result_age": latencies["capture_to_result_age_ms"].data[-1]}}
            log.write(json.dumps(row, separators=(",", ":")) + "\n")
            previous_target_id = target_id; previous_target_state = target_state; rows.append(row)

    capture.stop(); ended = time.monotonic(); final_capture = capture.stats()
    hw["memory_after"] = meminfo(); hw["temperature_after"] = vcgencmd("measure_temp"); hw["throttling_after"] = vcgencmd("get_throttled")
    summary = {"status": "LIVE_TARGET_RUN_COMPLETE" if rows and not events["TIMESTAMP_ERROR"] else "LIVE_TARGET_TRACKING_BLOCKED", "target_seen": bool(counts["high_detection_frames"] or counts["low_detection_frames"] or counts["target_observed_frames"] or counts["prediction_only_frames"]), "duration_requested_s": duration, "duration_wall_s": ended - started, "frames_captured": final_capture["captured"], "frames_processed": len(rows), "frames_dropped": {"queue_stale_newest_policy": final_capture["stale_queue_drops"], "capture_read_failures": final_capture["capture_read_failures"], "invalid_frame_dimensions": final_capture["invalid_frames"]}, "camera": {"device": cfg["device"], "source_resolution": sorted({tuple(row["source_resolution"]) for row in rows}), "requested": {"width": cfg["width"], "height": cfg["height"], "fps": cfg["fps"], "pixel_format": "MJPG"}}, "counts": counts, "track_ids_created": sorted(track_ids), "events": {key: {"count": len(value), "frames": value} for key, value in events.items()}, "target_center_error": {"x_px": {"min": min(error_x_px) if error_x_px else None, "max": max(error_x_px) if error_x_px else None}, "y_px": {"min": min(error_y_px) if error_y_px else None, "max": max(error_y_px) if error_y_px else None}, "x_norm": {"min": min(error_x_norm) if error_x_norm else 0.0, "max": max(error_x_norm) if error_x_norm else 0.0}, "y_norm": {"min": min(error_y_norm) if error_y_norm else 0.0, "max": max(error_y_norm) if error_y_norm else 0.0}}, "command_characterization": {"samples": len(rows), "raw_pan": {"min": min(raw_pan) if raw_pan else 0.0, "max": max(raw_pan) if raw_pan else 0.0}, "raw_tilt": {"min": min(raw_tilt) if raw_tilt else 0.0, "max": max(raw_tilt) if raw_tilt else 0.0}, "rate_limited_pan": {"min": min(command_pan) if command_pan else 0.0, "max": max(command_pan) if command_pan else 0.0}, "rate_limited_tilt": {"min": min(command_tilt) if command_tilt else 0.0, "max": max(command_tilt) if command_tilt else 0.0}, "rate_limit_events": len(events["RATE_LIMIT"]), "neutral_transitions": neutral_transitions}, "latency_ms": {key: stats(value) for key, value in latencies.items()}, "fps": {"capture": (final_capture["captured"] - 1) / (final_capture["last_capture_timestamp"] - final_capture["first_capture_timestamp"]) if final_capture["captured"] > 1 and final_capture["last_capture_timestamp"] and final_capture["first_capture_timestamp"] and final_capture["last_capture_timestamp"] > final_capture["first_capture_timestamp"] else 0.0, "processing": len(rows) / (ended - started) if ended > started else 0.0}, "hardware": hw, "peak_rss_kb": rss_kb(), "detector": {"backend": "NCNN", "precision": "FP32", "param_sha256": expected_param, "bin_sha256": expected_bin, "public_threshold": 0.25, "tracker_floor": 0.10, "nms_iou": 0.70, "single_inference_per_processed_frame": True, "one_nms_per_processed_frame": True}, "tracker_profile": "bytetrack_motion_adaptive", "preview_envelope": cfg.get("preview_envelope", {}), "actuator": {"mode": "DRY_RUN_ONLY", "enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0, "servo_writes": 0, "motor_writes": 0}, "test_accessed": False, "target_source": cfg.get("target_source", {})}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"status": summary["status"], "target_seen": summary["target_seen"], "frames_captured": summary["frames_captured"], "frames_processed": summary["frames_processed"], "counts": counts, "track_ids": sorted(track_ids), "fps": summary["fps"], "latency": summary["latency_ms"]["total_processing_ms"], "actuator": summary["actuator"]}, indent=2), flush=True)
    return 0 if summary["status"] == "LIVE_TARGET_RUN_COMPLETE" and summary["target_seen"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
