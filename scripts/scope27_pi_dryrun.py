#!/usr/bin/env python3
"""Scope 27 frozen NCNN -> existing ByteTrack dry-run on an offline video."""
from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path

import cv2
import numpy as np

from scope21_pi_runner import decode, letterbox, meminfo, vcgencmd

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from anti_drone.tracking import ByteTrack, ByteTrackConfig, Detection, TrackState  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class FrozenNcnnDetector:
    def __init__(self, model_dir: Path):
        import ncnn

        self.ncnn = ncnn
        self.net = ncnn.Net()
        self.net.opt.use_vulkan_compute = False
        self.net.opt.num_threads = 4
        self.net.load_param(str(model_dir / "model.ncnn.param"))
        self.net.load_model(str(model_dir / "model.ncnn.bin"))

    def infer(self, frame: np.ndarray) -> tuple[list[Detection], dict, dict]:
        pre_start = time.perf_counter()
        boxed, gain, pad = letterbox(frame, 480)
        rgb = cv2.cvtColor(boxed, cv2.COLOR_BGR2RGB)
        tensor = np.ascontiguousarray(rgb.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
        preprocess_ms = (time.perf_counter() - pre_start) * 1000.0

        infer_start = time.perf_counter()
        rgb_u8 = np.ascontiguousarray(np.clip(tensor[0].transpose(1, 2, 0) * 255.0, 0, 255).astype(np.uint8))
        mat = self.ncnn.Mat.from_pixels(rgb_u8, self.ncnn.Mat.PixelType.PIXEL_RGB, 480, 480)
        mat.substract_mean_normalize(np.zeros(3, dtype=np.float32), np.ones(3, dtype=np.float32) / 255.0)
        extractor = self.net.create_extractor()
        extractor.input("in0", mat)
        status, output = extractor.extract("out0")
        if status != 0:
            raise RuntimeError(f"NCNN inference failed with status {status}")
        raw = np.asarray(output)[None, ...]
        inference_ms = (time.perf_counter() - infer_start) * 1000.0

        post_start = time.perf_counter()
        detections, contract = decode(raw, gain, pad, frame.shape[:2])
        postprocess_ms = (time.perf_counter() - post_start) * 1000.0
        converted = [Detection(np.asarray(item["bbox"], dtype=np.float32), float(item["confidence"]), int(item["class"])) for item in detections]
        return converted, contract, {"preprocess_ms": preprocess_ms, "inference_ms": inference_ms, "postprocess_ms": postprocess_ms}


class DryRunActuator:
    """Preview-only sink: it never imports or writes GPIO/PWM/serial output."""

    enabled = False

    def preview(self, track, frame_shape: tuple[int, int]) -> dict:
        height, width = frame_shape
        if track is None:
            return {"mode": "DRY_RUN_ONLY", "actuator_output_enabled": False, "selected_target": None, "pan_error_px": None, "tilt_error_px": None}
        box = np.asarray(track.box, dtype=np.float32)
        center_x = float((box[0] + box[2]) / 2.0)
        center_y = float((box[1] + box[3]) / 2.0)
        return {"mode": "DRY_RUN_ONLY", "actuator_output_enabled": False, "selected_target": track.track_id, "target_center": [center_x, center_y], "pan_error_px": center_x - width / 2.0, "tilt_error_px": center_y - height / 2.0, "command_value": None}


def select_target(tracks):
    active = [track for track in tracks if track.state != TrackState.REMOVED]
    observed = [track for track in active if track.is_observed]
    candidates = observed or active
    return max(candidates, key=lambda track: (float(track.confidence), -int(track.track_id)), default=None)


def valid_box(box, shape):
    height, width = shape
    return len(box) == 4 and np.isfinite(box).all() and 0 <= box[0] <= box[2] <= width and 0 <= box[1] <= box[3] <= height


def main() -> int:
    config = json.loads(Path("config.json").read_text())
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    sequence = json.loads(Path(config["sequence_manifest"]).read_text())
    if len(sequence) != 301:
        raise SystemExit(f"sequence frame count mismatch: {len(sequence)}")
    hardware = {"uname": platform.uname()._asdict(), "machine": platform.machine(), "model": Path("/proc/device-tree/model").read_text(errors="replace").strip("\x00\n") if Path("/proc/device-tree/model").exists() else None, "memory_before": meminfo(), "temperature_before": vcgencmd("measure_temp"), "throttling_before": vcgencmd("get_throttled")}
    result = {"status": "DRY_RUN_COMPLETE", "sequence_id": config["sequence_id"], "frames_expected": len(sequence), "frames_processed": 0, "detector": {"candidate_id": config["candidate_id"], "backend": "NCNN", "precision": "FP32", "imgsz": 480, "confidence": 0.25, "nms_iou": 0.70, "param_sha256": config["param_sha256"], "bin_sha256": config["bin_sha256"]}, "tracker_profile": "bytetrack_motion_adaptive", "tracker_config": config["tracker_config"], "actuator": {"mode": "DRY_RUN_ONLY", "enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0}, "hardware": hardware, "events": {}, "track_ids_created": [], "test_accessed": False}
    if hardware["machine"] != "aarch64" or "Raspberry Pi 5 Model B Rev 1.0" not in (hardware["model"] or ""):
        result["status"] = "PI_IDENTITY_FAIL"
        Path(output_dir / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        return 2
    if sha256(Path(config["model_dir"]) / "model.ncnn.param") != config["param_sha256"] or sha256(Path(config["model_dir"]) / "model.ncnn.bin") != config["bin_sha256"]:
        result["status"] = "DETECTOR_ARTIFACT_HASH_FAIL"
        Path(output_dir / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        return 2

    detector = FrozenNcnnDetector(Path(config["model_dir"]))
    tracker = ByteTrack(ByteTrackConfig(**config["tracker_config"]), mode="motion_adaptive")
    actuator = DryRunActuator()
    capture = cv2.VideoCapture(config["video"])
    if not capture.isOpened():
        raise SystemExit("offline video open failed")
    rows = []
    latencies = {key: [] for key in ("decode_read_ms", "preprocess_ms", "inference_ms", "postprocess_ms", "tracker_update_ms", "target_selection_ms", "total_pipeline_ms")}
    events = {key: [] for key in ("DETECTOR_NO_DETECTION", "TRACK_NOT_CREATED", "TRACK_LOST", "TRACK_REACQUIRED", "ID_SWITCH", "TARGET_SWITCH", "TARGET_NULL", "COORDINATE_ERROR", "TIMESTAMP_ERROR")}
    created_ids = set()
    previous_timestamp = None
    previous_selected_id = None
    previous_observed_id = None
    previous_target_state = None
    ever_had_target = False
    source_index = 0
    with (output_dir / "target_state.jsonl").open("w") as log:
        while True:
            total_start = time.perf_counter()
            read_start = time.perf_counter()
            ok, frame = capture.read()
            decode_ms = (time.perf_counter() - read_start) * 1000.0
            if not ok:
                break
            if source_index >= len(sequence):
                raise RuntimeError("video has more frames than locked sequence manifest")
            item = sequence[source_index]
            frame_id = int(item["frame_id"])
            timestamp = float(item["timestamp"])
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                events["TIMESTAMP_ERROR"].append(frame_id)
            previous_timestamp = timestamp
            detections, contract, timing = detector.infer(frame)
            tracker_start = time.perf_counter()
            tracks = tracker.update(detections, timestamp=timestamp, frame_id=frame_id, source_frame_id=frame_id)
            tracker_ms = (time.perf_counter() - tracker_start) * 1000.0
            target_start = time.perf_counter()
            target = select_target(tracks)
            target_ms = (time.perf_counter() - target_start) * 1000.0
            command = actuator.preview(target, frame.shape[:2])
            track_ids = sorted(int(track.track_id) for track in tracks)
            created_ids.update(track_ids)
            observed = [track for track in tracks if track.is_observed]
            observed_id = target.track_id if target is not None and target.is_observed else None
            if not detections:
                events["DETECTOR_NO_DETECTION"].append(frame_id)
            if detections and not tracks:
                events["TRACK_NOT_CREATED"].append(frame_id)
            current_target_state = "observed" if target is not None and target.is_observed else "predicted" if target is not None else None
            if target is None:
                events["TARGET_NULL"].append(frame_id)
                if previous_target_state is not None:
                    events["TRACK_LOST"].append(frame_id)
            elif current_target_state == "predicted" and previous_target_state == "observed":
                events["TRACK_LOST"].append(frame_id)
            elif current_target_state == "observed" and previous_target_state in {None, "predicted"} and ever_had_target:
                events["TRACK_REACQUIRED"].append(frame_id)
            if previous_observed_id is not None and observed_id is not None and observed_id != previous_observed_id:
                events["ID_SWITCH"].append(frame_id)
            if previous_selected_id is not None and target is not None and target.track_id != previous_selected_id and not (previous_observed_id is not None and observed_id is not None):
                events["TARGET_SWITCH"].append(frame_id)
            for track in tracks:
                if not valid_box(track.box, frame.shape[:2]):
                    events["COORDINATE_ERROR"].append(frame_id)
            total_ms = (time.perf_counter() - total_start) * 1000.0
            latencies["decode_read_ms"].append(decode_ms)
            for key in ("preprocess_ms", "inference_ms", "postprocess_ms"):
                latencies[key].append(float(timing[key]))
            latencies["tracker_update_ms"].append(tracker_ms)
            latencies["target_selection_ms"].append(target_ms)
            latencies["total_pipeline_ms"].append(total_ms)
            row = {"frame_id": frame_id, "timestamp": timestamp, "detector_count": len(detections), "detector_contract": contract, "track_count": len(tracks), "track_ids": track_ids, "selected_target_id": int(target.track_id) if target is not None else None, "target_bbox": [float(value) for value in target.box] if target is not None else None, "target_confidence": float(target.confidence) if target is not None else None, "target_center": [float((target.box[0] + target.box[2]) / 2.0), float((target.box[1] + target.box[3]) / 2.0)] if target is not None else None, "target_observation": "observed" if target is not None and target.is_observed else "predicted" if target is not None else None, "target_state": target.state.value if target is not None else None, "lost_age_seconds": float(target.missed_seconds) if target is not None else None, "latency_ms": {"decode_read": decode_ms, "preprocess": timing["preprocess_ms"], "inference": timing["inference_ms"], "postprocess": timing["postprocess_ms"], "tracker_update": tracker_ms, "target_selection": target_ms, "total_pipeline": total_ms}, "command_preview": command}
            log.write(json.dumps(row, separators=(",", ":")) + "\n")
            rows.append(row)
            previous_selected_id = target.track_id if target is not None else None
            previous_observed_id = observed_id
            previous_target_state = current_target_state
            ever_had_target = ever_had_target or target is not None
            source_index += 1
    capture.release()
    if source_index != len(sequence):
        result["status"] = "OFFLINE_RUN_INCOMPLETE"
    hardware["memory_after"] = meminfo()
    hardware["temperature_after"] = vcgencmd("measure_temp")
    hardware["throttling_after"] = vcgencmd("get_throttled")
    result["hardware"] = hardware
    result["frames_processed"] = len(rows)
    result["track_ids_created"] = sorted(created_ids)
    result["events"] = {key: {"count": len(value), "frames": value} for key, value in events.items()}
    result["latency_ms"] = {key: {"mean": float(np.mean(value)) if value else 0.0, "p50": float(np.percentile(value, 50)) if value else 0.0, "p95": float(np.percentile(value, 95)) if value else 0.0} for key, value in latencies.items()}
    result["effective_fps"] = 1000.0 / result["latency_ms"]["total_pipeline_ms"]["mean"] if result["latency_ms"]["total_pipeline_ms"]["mean"] else 0.0
    result["target_state_summary"] = {"observed_frames": sum(row["target_observation"] == "observed" for row in rows), "predicted_only_frames": sum(row["target_observation"] == "predicted" for row in rows), "no_target_frames": sum(row["selected_target_id"] is None for row in rows), "id_changes": len(events["ID_SWITCH"]), "reacquisition_events": len(events["TRACK_REACQUIRED"])}
    Path(output_dir / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "frames": result["frames_processed"], "track_ids": result["track_ids_created"], "events": {key: value["count"] for key, value in result["events"].items()}, "latency_ms": result["latency_ms"], "effective_fps": result["effective_fps"], "actuator": result["actuator"], "hardware": {key: hardware.get(key) for key in ("model", "temperature_before", "temperature_after", "throttling_before", "throttling_after")}}, indent=2), flush=True)
    return 0 if result["status"] == "DRY_RUN_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
