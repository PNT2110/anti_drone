#!/usr/bin/env python3
"""Scope 29 bounded-queue USB webcam live dry-run on Raspberry Pi 5."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import queue
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from scope21_pi_runner import meminfo, vcgencmd
from scope28_pi_runner import DryRunActuator, FrozenNcnnDetector, association_source, select_target, valid_box
from anti_drone.tracking import ByteTrack, ByteTrackConfig, Detection


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rss_kb() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return -1


class RingSamples:
    """Bounded deterministic rolling samples for long live telemetry."""

    def __init__(self, capacity: int = 2048):
        self.capacity = capacity
        self.data: list[float] = []
        self.cursor = 0

    def append(self, value: float) -> None:
        if len(self.data) < self.capacity:
            self.data.append(float(value))
        else:
            self.data[self.cursor] = float(value)
            self.cursor = (self.cursor + 1) % self.capacity


def valid_capture_frame(frame, width: int, height: int) -> bool:
    return frame is not None and getattr(frame, "ndim", 0) == 3 and tuple(getattr(frame, "shape", ())) == (height, width, 3)


def hardware():
    return {"uname": platform.uname()._asdict(), "machine": platform.machine(), "model": Path("/proc/device-tree/model").read_text(errors="replace").strip("\x00\n") if Path("/proc/device-tree/model").exists() else None, "memory_before": meminfo(), "temperature_before": vcgencmd("measure_temp"), "throttling_before": vcgencmd("get_throttled")}


class LiveCapture:
    def __init__(self, device: str, width: int, height: int, fps: int, max_consecutive_failures: int = 5):
        self.device = device
        self.width, self.height, self.fps = width, height, fps
        self.max_consecutive_failures = max_consecutive_failures
        self.items: queue.Queue = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.cap = None
        self.lock = threading.Lock()
        self.captured = 0
        self.stale_drops = 0
        self.read_failures = 0
        self.invalid_frames = 0
        self.consecutive_failures = 0
        self.first_capture_timestamp: float | None = None
        self.last_capture_timestamp: float | None = None
        self.error: str | None = None
        self.actual: dict = {}

    def open(self) -> bool:
        source = int(self.device) if self.device.isdigit() else self.device
        self.cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.error = "CAMERA_OPEN_FAILED"
            return False
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self.actual = {"width": int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "height": int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), "fps_property": float(self.cap.get(cv2.CAP_PROP_FPS)), "fourcc": int(self.cap.get(cv2.CAP_PROP_FOURCC))}
        return True

    def start(self):
        if self.cap is None and not self.open():
            return
        self.thread = threading.Thread(target=self._loop, name="scope29-capture", daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.stop_event.is_set():
            started = time.monotonic()
            ok, frame = self.cap.read()
            read_ms = (time.monotonic() - started) * 1000.0
            now = time.monotonic()
            if not ok or frame is None or frame.size == 0:
                with self.lock:
                    self.read_failures += 1
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.max_consecutive_failures:
                        self.error = "FRAME_READ_FAILED"
                        self.stop_event.set()
                continue
            # Own the capture buffer before handing it to the bounded queue.
            # Some V4L2/OpenCV paths reuse the producer buffer on the next read.
            frame = frame.copy()
            if not valid_capture_frame(frame, self.width, self.height):
                with self.lock:
                    self.invalid_frames += 1
                continue
            with self.lock:
                self.consecutive_failures = 0
                frame_id = self.captured + 1
                self.captured += 1
                if self.first_capture_timestamp is None:
                    self.first_capture_timestamp = now
                self.last_capture_timestamp = now
            item = {"capture_id": frame_id, "capture_timestamp_monotonic": now, "frame": frame, "capture_read_ms": read_ms}
            try:
                self.items.put_nowait(item)
            except queue.Full:
                try:
                    self.items.get_nowait()
                except queue.Empty:
                    pass
                with self.lock:
                    self.stale_drops += 1
                try:
                    self.items.put_nowait(item)
                except queue.Full:
                    with self.lock:
                        self.stale_drops += 1

    def get(self, timeout: float = 0.25):
        try:
            return self.items.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=3)
        if self.cap is not None:
            self.cap.release()

    def stats(self):
        with self.lock:
            return {"captured": self.captured, "stale_queue_drops": self.stale_drops, "capture_read_failures": self.read_failures, "invalid_frames": self.invalid_frames, "first_capture_timestamp": self.first_capture_timestamp, "last_capture_timestamp": self.last_capture_timestamp, "error": self.error, "actual": dict(self.actual)}


def percentile(values, q):
    return float(np.percentile(values, q)) if values else 0.0


def stats(values):
    data = values.data
    return {"mean": float(np.mean(data)) if data else 0.0, "p50": percentile(data, 50), "p95": percentile(data, 95), "sample_count": len(data), "sample_policy": "bounded_rolling_2048"}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", type=Path, required=True); parser.add_argument("--mode", choices=("smoke", "sustained"), required=True)
    args = parser.parse_args(); cfg = json.loads(args.config.read_text()); output = Path(cfg["output_dir"]); output.mkdir(parents=True, exist_ok=True)
    hw = hardware()
    if hw["machine"] != "aarch64" or "Raspberry Pi 5 Model B Rev 1.0" not in (hw["model"] or ""):
        raise SystemExit("PI_IDENTITY_FAIL")
    model = Path(cfg["model_dir"])
    if sha256(model / "model.ncnn.param") != cfg["param_sha256"] or sha256(model / "model.ncnn.bin") != cfg["bin_sha256"]:
        raise SystemExit("DETECTOR_ARTIFACT_HASH_FAIL")
    capture = LiveCapture(cfg["device"], int(cfg["width"]), int(cfg["height"]), int(cfg["fps"]))
    if not capture.open():
        result = {"status": capture.error or "CAMERA_OPEN_FAILED", "camera": {"device": cfg["device"]}, "actuator": {"mode": "DRY_RUN_ONLY", "enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0}, "model_loaded": False}
        (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        return 2
    detector = FrozenNcnnDetector(model)
    tracker = ByteTrack(ByteTrackConfig(**cfg["tracker_config"]), mode="motion_adaptive")
    actuator = DryRunActuator()
    capture.start()
    duration = float(cfg["duration_s"])
    started = time.monotonic(); deadline = started + duration
    latencies = {key: RingSamples() for key in ("queue_wait_ms", "preprocess_ms", "inference_ms", "candidate_decode_ms", "nms_ms", "stream_split_ms", "postprocess_ms", "tracker_update_ms", "target_selection_ms", "overlay_render_ms", "total_processing_ms", "capture_to_result_age_ms")}
    processed_count = 0; source_resolutions = set(); target_ids = set(); association_counts = {"HIGH": 0, "LOW": 0, "PREDICTED": 0, "OBSERVED_UNRESOLVED": 0}; errors = []
    previous_ts = None; previous_target_id = None; previous_state = None; frame_index = 0; thermal = []
    log_path = output / "live_state.jsonl"
    with log_path.open("w") as log:
        while time.monotonic() < deadline:
            item = capture.get(timeout=0.25)
            now = time.monotonic()
            if item is None:
                if capture.error:
                    errors.append({"type": capture.error, "time": now})
                    break
                continue
            frame_index += 1; processed_count += 1; frame = item["frame"]; source_resolutions.add((int(frame.shape[1]), int(frame.shape[0]))); timestamp = float(item["capture_timestamp_monotonic"])
            if previous_ts is not None and timestamp <= previous_ts:
                errors.append({"type": "TIMESTAMP_ERROR", "frame_id": item["capture_id"]})
            previous_ts = timestamp
            process_start = time.monotonic()
            streams = detector.infer_dual(frame)
            tracker_start = time.monotonic(); tracks = tracker.update([Detection(np.asarray(row["bbox"], dtype=np.float32), float(row["confidence"]), int(row["class"])) for row in streams["all"]], timestamp=timestamp, frame_id=item["capture_id"], source_frame_id=item["capture_id"]); tracker_ms = (time.monotonic() - tracker_start) * 1000.0
            target_start = time.monotonic(); target = select_target(tracks); target_ms = (time.monotonic() - target_start) * 1000.0
            render_start = time.monotonic(); command = actuator.preview(target, frame.shape[:2]); render_ms = (time.monotonic() - render_start) * 1000.0
            source = association_source(target, streams["high"], streams["low"]); association_counts[source] = association_counts.get(source, 0) + 1 if source else association_counts.get(source, 0)
            track_ids = sorted(int(track.track_id) for track in tracks); target_ids.update(track_ids)
            target_state = "NONE" if target is None else "PREDICTED" if not target.is_observed else "LOW_ASSOCIATED_INFERRED" if source == "LOW" else "OBSERVED"
            total_ms = (time.monotonic() - process_start) * 1000.0; age_ms = (time.monotonic() - timestamp) * 1000.0
            latencies["queue_wait_ms"].append((process_start - timestamp) * 1000.0)
            for key in ("preprocess_ms", "inference_ms", "candidate_decode_ms", "nms_ms", "stream_split_ms", "postprocess_ms"): latencies[key].append(float(streams["timing"][key]))
            latencies["tracker_update_ms"].append(tracker_ms); latencies["target_selection_ms"].append(target_ms); latencies["overlay_render_ms"].append(render_ms); latencies["total_processing_ms"].append(total_ms); latencies["capture_to_result_age_ms"].append(age_ms)
            row = {"frame_id": int(item["capture_id"]), "capture_timestamp_monotonic": timestamp, "source_resolution": [int(frame.shape[1]), int(frame.shape[0])], "high_count": len(streams["high"]), "low_count": len(streams["low"]), "high_detections": streams["high"], "low_detections": streams["low"], "track_ids": track_ids, "selected_target_id": int(target.track_id) if target is not None else None, "target_bbox": [float(x) for x in target.box] if target is not None else None, "target_center": [float((target.box[0] + target.box[2]) / 2), float((target.box[1] + target.box[3]) / 2)] if target is not None else None, "target_confidence": float(target.confidence) if target is not None else None, "target_state": target_state, "target_association_source": source, "latency_ms": {"capture_read": item["capture_read_ms"], "queue_wait": latencies["queue_wait_ms"].data[-1], **{key.replace("_ms", ""): float(streams["timing"][key]) for key in ("preprocess_ms", "inference_ms", "candidate_decode_ms", "nms_ms", "stream_split_ms", "postprocess_ms")}, "tracker_update": tracker_ms, "target_selection": target_ms, "overlay_render": render_ms, "total_processing": total_ms, "capture_to_result_age": age_ms}, "command_preview": command, "actuator_output_enabled": False, "dry_run": True}
            log.write(json.dumps(row, separators=(",", ":")) + "\n")
            if processed_count % 300 == 0:
                thermal.append({"elapsed_s": time.monotonic() - started, "temperature": vcgencmd("measure_temp"), "throttling": vcgencmd("get_throttled"), "rss_kb": rss_kb(), "memory": meminfo()})
            previous_target_id = int(target.track_id) if target is not None else None; previous_state = target_state
    capture.stop(); final = capture.stats(); ended = time.monotonic(); hw["memory_after"] = meminfo(); hw["temperature_after"] = vcgencmd("measure_temp"); hw["throttling_after"] = vcgencmd("get_throttled")
    first_capture = final["first_capture_timestamp"]; last_capture = final["last_capture_timestamp"]; capture_fps = (final["captured"] - 1) / (last_capture - first_capture) if final["captured"] > 1 and last_capture and first_capture and last_capture > first_capture else 0.0
    processing_duration = ended - started; processing_fps = processed_count / processing_duration if processing_duration > 0 else 0.0
    run_status = ("LIVE_SMOKE_COMPLETE" if args.mode == "smoke" else "LIVE_SUSTAINED_COMPLETE") if not errors and (ended - started) >= duration * 0.95 else "LIVE_PIPELINE_UNSTABLE"
    summary = {"status": run_status, "mode": args.mode, "duration_requested_s": duration, "duration_wall_s": ended - started, "frames_captured": final["captured"], "frames_processed": processed_count, "frames_dropped": {"queue_stale_newest_policy": final["stale_queue_drops"], "capture_read_failures": final["capture_read_failures"], "invalid_frame_dimensions": final["invalid_frames"], "processing_skips": 0, "display_drops": 0}, "camera": {"device": cfg["device"], "requested": {"width": cfg["width"], "height": cfg["height"], "fps": cfg["fps"], "pixel_format": "MJPG"}, "actual_properties": final["actual"], "source_resolution": sorted(source_resolutions)}, "fps": {"camera_capture_fps": capture_fps, "pipeline_processing_fps": processing_fps, "display_fps": 0.0, "reference_offline_scope28_fps": 22.7375}, "latency_ms": {key: stats(value) for key, value in latencies.items()}, "track_ids_created": sorted(target_ids), "association_counts": association_counts, "errors": errors, "hardware": hw, "thermal_samples": thermal, "peak_rss_kb": max([rss_kb()] + [int(sample["rss_kb"]) for sample in thermal]), "actuator": {"mode": "DRY_RUN_ONLY", "enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0}, "detector": {"backend": "NCNN", "precision": "FP32", "param_sha256": cfg["param_sha256"], "bin_sha256": cfg["bin_sha256"], "single_inference_per_captured_frame": True, "one_nms_per_inference": True}, "tracker_profile": "bytetrack_motion_adaptive", "queue_policy": {"maxsize": 1, "drop_policy": "drop_stale_keep_newest", "unbounded": False}, "webcam": True, "display": "headless_log_only", "test_accessed": False, "actuator_output_enabled": False}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"status": summary["status"], "frames_captured": summary["frames_captured"], "frames_processed": summary["frames_processed"], "drops": summary["frames_dropped"], "capture_fps": capture_fps, "processing_fps": processing_fps, "latency": summary["latency_ms"]["total_processing_ms"], "temp": [hw.get("temperature_before"), hw.get("temperature_after")], "throttling": [hw.get("throttling_before"), hw.get("throttling_after")]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
