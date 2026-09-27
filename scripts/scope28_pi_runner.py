#!/usr/bin/env python3
"""Scope 28 Pi runner: one NCNN inference, one adapter NMS, two streams."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import cv2
import numpy as np

from scope21_pi_runner import decode as legacy_decode
from scope21_pi_runner import letterbox, meminfo, scale_box, vcgencmd

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from anti_drone.scope28_contract import compare_detections, nms_candidates, select_single_drone_observation, split_kept_observations, suppress_contained_duplicates, box_iou  # noqa: E402
from anti_drone.tracking import ByteTrack, ByteTrackConfig, Detection, TrackState  # noqa: E402


PUBLIC_THRESHOLD = 0.25
TRACKER_FLOOR = 0.10
NMS_IOU = 0.70


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def valid_box(box, shape):
    height, width = shape
    return len(box) == 4 and np.isfinite(box).all() and 0 <= box[0] <= box[2] <= width and 0 <= box[1] <= box[3] <= height


class FrozenNcnnDetector:
    def __init__(self, model_dir: Path):
        import ncnn

        self.ncnn = ncnn
        self.net = ncnn.Net()
        self.net.opt.use_vulkan_compute = False
        self.net.opt.num_threads = 4
        self.net.load_param(str(model_dir / "model.ncnn.param"))
        self.net.load_model(str(model_dir / "model.ncnn.bin"))
        manifest_path = model_dir / "model_manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        self.contained_duplicate_suppression = bool(manifest.get("suppress_contained_duplicates", False))
        self.single_drone_observation = manifest.get("identity_mode") == "SINGLE_DRONE_SESSION"

    def _network(self, frame: np.ndarray):
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
        return raw, gain, pad, preprocess_ms, inference_ms

    @staticmethod
    def _candidates(raw: np.ndarray, gain: float, pad, shape):
        raw = np.asarray(raw, dtype=np.float32)
        if raw.ndim != 3 or raw.shape[1] != 5:
            raise ValueError(f"Scope 28 requires frozen [1,5,N] output, got {raw.shape}")
        rows = []
        for cx, cy, width, height, confidence in raw[0].T:
            confidence = float(confidence)
            if confidence < TRACKER_FLOOR:
                continue
            box = [float(cx - width / 2), float(cy - height / 2), float(cx + width / 2), float(cy + height / 2)]
            rows.append({"class": 0, "confidence": confidence, "bbox": scale_box(box, gain, pad, shape)})
        return rows, int(raw.shape[2]), list(raw.shape)

    def infer_dual(self, frame: np.ndarray, preferred_point: tuple[float, float] | None = None):
        raw, gain, pad, pre_ms, inf_ms = self._network(frame)
        post_start = time.perf_counter()
        candidate_start = time.perf_counter()
        candidates, raw_count, raw_shape = self._candidates(raw, gain, pad, frame.shape[:2])
        candidate_decode_ms = (time.perf_counter() - candidate_start) * 1000.0
        nms_start = time.perf_counter()
        kept = nms_candidates(candidates, NMS_IOU)
        nms_ms = (time.perf_counter() - nms_start) * 1000.0
        contained_duplicates_suppressed = 0
        if self.contained_duplicate_suppression:
            kept, contained_duplicates_suppressed = suppress_contained_duplicates(kept)
        split_start = time.perf_counter()
        high, low = split_kept_observations(kept, public_threshold=PUBLIC_THRESHOLD, tracker_floor=TRACKER_FLOOR)
        single_drone_candidates_suppressed = 0
        if self.single_drone_observation:
            high, low, single_drone_candidates_suppressed = select_single_drone_observation(
                high,
                low,
                preferred_point=preferred_point,
            )
        split_ms = (time.perf_counter() - split_start) * 1000.0
        post_ms = (time.perf_counter() - post_start) * 1000.0
        return {"raw": raw, "high": high, "low": low, "all": high + low, "contract": {"raw_shape": raw_shape, "xywh": True, "nms_embedded": False, "nms_applications": 1, "raw_candidate_count": raw_count, "floor_candidate_count": len(candidates), "contained_duplicates_suppressed": contained_duplicates_suppressed, "single_drone_candidates_suppressed": single_drone_candidates_suppressed, "single_drone_observation": self.single_drone_observation, "manual_anchor": list(preferred_point) if preferred_point is not None else None, "manual_anchor_matched": bool(preferred_point is not None and (high or low)), "high_count": len(high), "low_count": len(low), "public_threshold": PUBLIC_THRESHOLD, "tracker_floor": TRACKER_FLOOR, "nms_iou": NMS_IOU}, "timing": {"preprocess_ms": pre_ms, "inference_ms": inf_ms, "candidate_decode_ms": candidate_decode_ms, "nms_ms": nms_ms, "stream_split_ms": split_ms, "postprocess_ms": post_ms}}

    def infer_legacy(self, frame: np.ndarray):
        raw, gain, pad, pre_ms, inf_ms = self._network(frame)
        started = time.perf_counter()
        detections, contract = legacy_decode(raw, gain, pad, frame.shape[:2])
        return detections, contract, {"preprocess_ms": pre_ms, "inference_ms": inf_ms, "postprocess_ms": (time.perf_counter() - started) * 1000.0}


def select_target(tracks):
    active = [track for track in tracks if track.state != TrackState.REMOVED]
    observed = [track for track in active if track.is_observed]
    return max(observed or active, key=lambda track: (float(track.confidence), -int(track.track_id)), default=None)


def association_source(track, high, low):
    if track is None or not track.is_observed:
        return "PREDICTED" if track is not None else None
    for row in high:
        if box_iou([float(x) for x in track.box], row["bbox"]) >= 0.999:
            return "HIGH"
    for row in low:
        if box_iou([float(x) for x in track.box], row["bbox"]) >= 0.999:
            return "LOW"
    return "OBSERVED_UNRESOLVED"


class DryRunActuator:
    enabled = False

    def preview(self, track, frame_shape):
        height, width = frame_shape
        if track is None:
            return {"mode": "DRY_RUN_ONLY", "actuator_output_enabled": False, "selected_target": None, "pan_error_px": None, "tilt_error_px": None, "gpio_write": False, "pwm_write": False, "serial_write": False}
        box = np.asarray(track.box, dtype=np.float32)
        center_x, center_y = float((box[0] + box[2]) / 2), float((box[1] + box[3]) / 2)
        return {"mode": "DRY_RUN_ONLY", "actuator_output_enabled": False, "selected_target": int(track.track_id), "target_center": [center_x, center_y], "pan_error_px": center_x - width / 2.0, "tilt_error_px": center_y - height / 2.0, "command_value": None, "gpio_write": False, "pwm_write": False, "serial_write": False}


def hardware_snapshot():
    return {"uname": platform.uname()._asdict(), "machine": platform.machine(), "model": Path("/proc/device-tree/model").read_text(errors="replace").strip("\x00\n") if Path("/proc/device-tree/model").exists() else None, "memory_before": meminfo(), "temperature_before": vcgencmd("measure_temp"), "throttling_before": vcgencmd("get_throttled")}


def run_parity(detector, cfg, output):
    reference = json.loads(Path(cfg["reference"]).read_text())
    reference_by_key = {(row["run_id"], row["image"]): row for row in reference["records"]}
    images = []
    status = "PARITY_PASS"
    for item in cfg["images"]:
        image = cv2.imread(str(Path(cfg["input_root"]) / item["filename"]))
        if image is None:
            status = "PARITY_FAIL"
            images.append({"image": item["filename"], "status": "IMAGE_READ_FAIL"})
            continue
        streams = detector.infer_dual(image)
        comparison = compare_detections(reference_by_key[(cfg["run_id"], item["filename"])]["detections"], streams["high"])
        images.append({"image": item["filename"], "contract": streams["contract"], "parity": comparison})
        if comparison["status"] != "PARITY_PASS":
            status = "PARITY_FAIL"
    result = {"status": status, "candidate_id": cfg["candidate_id"], "images": images, "single_inference_per_image": True, "one_nms_per_image": True, "test_accessed": False}
    (output / "parity_8.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def capture_legacy_reference(detector, cfg, output):
    sequence = json.loads(Path(cfg["sequence_manifest"]).read_text())
    capture = cv2.VideoCapture(cfg["video"])
    if not capture.isOpened():
        raise RuntimeError("offline video open failed")
    rows = []
    for item in sequence:
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError("legacy reference video ended early")
        detections, contract, _ = detector.infer_legacy(frame)
        rows.append({"frame_id": int(item["frame_id"]), "timestamp": float(item["timestamp"]), "detections": detections, "contract": contract})
    capture.release()
    (output / "public_reference.jsonl").write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
    return len(rows)


def run_dual(detector, cfg, output):
    sequence = json.loads(Path(cfg["sequence_manifest"]).read_text())
    references = [json.loads(line) for line in (output / "public_reference.jsonl").read_text().splitlines()]
    if len(sequence) != 301 or len(references) != 301:
        raise RuntimeError("Scope 28 sequence/reference must contain 301 frames")
    tracker = ByteTrack(ByteTrackConfig(**cfg["tracker_config"]), mode="motion_adaptive")
    actuator = DryRunActuator()
    capture = cv2.VideoCapture(cfg["video"])
    if not capture.isOpened():
        raise RuntimeError("offline video open failed")
    rows = []
    latencies = {key: [] for key in ("decode_read_ms", "preprocess_ms", "inference_ms", "candidate_decode_ms", "nms_ms", "stream_split_ms", "postprocess_ms", "tracker_update_ms", "target_selection_ms", "total_pipeline_ms")}
    events = {key: [] for key in ("DETECTOR_NO_DETECTION", "LOW_ONLY_DETECTION", "TRACK_NOT_CREATED", "TRACK_LOST", "TRACK_REACQUIRED", "ID_SWITCH", "TARGET_SWITCH", "TARGET_NULL", "COORDINATE_ERROR", "TIMESTAMP_ERROR", "HIGH_STREAM_REGRESSION")}
    created_ids, association_counts = set(), {"HIGH": 0, "LOW": 0, "PREDICTED": 0, "OBSERVED_UNRESOLVED": 0}
    previous_timestamp = previous_selected_id = previous_observed_id = previous_state = None
    ever_had_target = False
    source_index = 0
    with (output / "target_state.jsonl").open("w") as log, (output / "stream_records.jsonl").open("w") as stream_log:
        while True:
            total_start = time.perf_counter()
            read_start = time.perf_counter(); ok, frame = capture.read(); decode_ms = (time.perf_counter() - read_start) * 1000.0
            if not ok:
                break
            item = sequence[source_index]
            frame_id, timestamp = int(item["frame_id"]), float(item["timestamp"])
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                events["TIMESTAMP_ERROR"].append(frame_id)
            previous_timestamp = timestamp
            streams = detector.infer_dual(frame)
            reference = references[source_index]["detections"]
            equivalence = compare_detections(reference, streams["high"])
            stream_record = {"frame_id": frame_id, "timestamp": timestamp, "raw_candidate_count": streams["contract"]["raw_candidate_count"], "high_count": len(streams["high"]), "low_count": len(streams["low"]), "high": streams["high"], "low": streams["low"], "high_equivalence": equivalence, "nms_applications": streams["contract"]["nms_applications"]}
            stream_log.write(json.dumps(stream_record, separators=(",", ":")) + "\n")
            if equivalence["status"] != "PARITY_PASS":
                events["HIGH_STREAM_REGRESSION"].append(frame_id)
            if not streams["high"]:
                events["DETECTOR_NO_DETECTION"].append(frame_id)
            if not streams["high"] and streams["low"]:
                events["LOW_ONLY_DETECTION"].append(frame_id)
            tracker_start = time.perf_counter(); tracks = tracker.update([Detection(np.asarray(row["bbox"], dtype=np.float32), float(row["confidence"]), int(row["class"])) for row in streams["all"]], timestamp=timestamp, frame_id=frame_id, source_frame_id=frame_id); tracker_ms = (time.perf_counter() - tracker_start) * 1000.0
            target_start = time.perf_counter(); target = select_target(tracks); target_ms = (time.perf_counter() - target_start) * 1000.0
            command = actuator.preview(target, frame.shape[:2])
            target_source = association_source(target, streams["high"], streams["low"])
            if target_source in association_counts:
                association_counts[target_source] += 1
            track_ids = sorted(int(track.track_id) for track in tracks); created_ids.update(track_ids)
            if streams["all"] and not tracks: events["TRACK_NOT_CREATED"].append(frame_id)
            observed_ids = [int(track.track_id) for track in tracks if track.is_observed]
            observed_id = int(target.track_id) if target is not None and target.is_observed else None
            current_state = "observed" if target is not None and target.is_observed else "predicted" if target is not None else None
            if target is None:
                events["TARGET_NULL"].append(frame_id)
                if previous_state is not None: events["TRACK_LOST"].append(frame_id)
            elif current_state == "predicted" and previous_state == "observed": events["TRACK_LOST"].append(frame_id)
            elif current_state == "observed" and previous_state in {None, "predicted"} and ever_had_target: events["TRACK_REACQUIRED"].append(frame_id)
            if previous_observed_id is not None and observed_id is not None and observed_id != previous_observed_id: events["ID_SWITCH"].append(frame_id)
            if previous_selected_id is not None and target is not None and int(target.track_id) != previous_selected_id and not (previous_observed_id is not None and observed_id is not None): events["TARGET_SWITCH"].append(frame_id)
            for track in tracks:
                if not valid_box(track.box, frame.shape[:2]): events["COORDINATE_ERROR"].append(frame_id)
            total_ms = (time.perf_counter() - total_start) * 1000.0
            latencies["decode_read_ms"].append(decode_ms)
            for key in ("preprocess_ms", "inference_ms", "candidate_decode_ms", "nms_ms", "stream_split_ms", "postprocess_ms"): latencies[key].append(float(streams["timing"][key]))
            latencies["tracker_update_ms"].append(tracker_ms); latencies["target_selection_ms"].append(target_ms); latencies["total_pipeline_ms"].append(total_ms)
            row = {"frame_id": frame_id, "timestamp": timestamp, "raw_candidate_count": streams["contract"]["raw_candidate_count"], "high_detections": streams["high"], "low_detections": streams["low"], "high_count": len(streams["high"]), "low_count": len(streams["low"]), "detector_count_to_tracker": len(streams["all"]), "track_count": len(tracks), "track_ids": track_ids, "track_association_sources": {str(track.track_id): association_source(track, streams["high"], streams["low"]) for track in tracks}, "selected_target_id": int(target.track_id) if target is not None else None, "target_bbox": [float(x) for x in target.box] if target is not None else None, "target_confidence": float(target.confidence) if target is not None else None, "target_observation": "observed" if target is not None and target.is_observed else "predicted" if target is not None else None, "target_association_source": target_source, "target_state": target.state.value if target is not None else None, "lost_age_seconds": float(target.missed_seconds) if target is not None else None, "latency_ms": {"decode_read": decode_ms, **{key.replace("_ms", ""): float(streams["timing"][key]) for key in ("preprocess_ms", "inference_ms", "candidate_decode_ms", "nms_ms", "stream_split_ms", "postprocess_ms")}, "tracker_update": tracker_ms, "target_selection": target_ms, "total_pipeline": total_ms}, "command_preview": command, "actuator_output_enabled": False}
            log.write(json.dumps(row, separators=(",", ":")) + "\n"); rows.append(row)
            previous_selected_id = int(target.track_id) if target is not None else None; previous_observed_id = observed_id; previous_state = current_state; ever_had_target = ever_had_target or target is not None; source_index += 1
    capture.release()
    hardware = {"memory_after": meminfo(), "temperature_after": vcgencmd("measure_temp"), "throttling_after": vcgencmd("get_throttled")}
    stats = {key: {"mean": float(np.mean(values)) if values else 0.0, "p50": float(np.percentile(values, 50)) if values else 0.0, "p95": float(np.percentile(values, 95)) if values else 0.0} for key, values in latencies.items()}
    summary = {"status": "HIGH_STREAM_REGRESSION" if events["HIGH_STREAM_REGRESSION"] else "DRY_RUN_COMPLETE", "frames_expected": 301, "frames_processed": len(rows), "tracker_profile": "bytetrack_motion_adaptive", "thresholds": {"public": PUBLIC_THRESHOLD, "tracker_floor": TRACKER_FLOOR, "track_low": 0.10, "track_high": 0.25, "new_track": 0.35, "nms_iou": NMS_IOU}, "events": {key: {"count": len(value), "frames": value} for key, value in events.items()}, "track_ids_created": sorted(created_ids), "association_counts": association_counts, "high_stream_equivalence": {"frames": len(rows), "pass_frames": len(rows) - len(events["HIGH_STREAM_REGRESSION"]), "fail_frames": len(events["HIGH_STREAM_REGRESSION"])}, "latency_ms": stats, "effective_fps": 1000.0 / stats["total_pipeline_ms"]["mean"] if stats["total_pipeline_ms"]["mean"] else 0.0, "stream_aggregates": {"frames_with_high": sum(row["high_count"] > 0 for row in rows), "frames_with_low": sum(row["low_count"] > 0 for row in rows), "low_only_frames": sum(row["high_count"] == 0 and row["low_count"] > 0 for row in rows), "high_boxes": sum(row["high_count"] for row in rows), "low_boxes": sum(row["low_count"] for row in rows)}, "target_state_summary": {"observed_frames": sum(row["target_observation"] == "observed" for row in rows), "predicted_only_frames": sum(row["target_observation"] == "predicted" for row in rows), "no_target_frames": sum(row["selected_target_id"] is None for row in rows), "id_changes": len(events["ID_SWITCH"]), "reacquisition_events": len(events["TRACK_REACQUIRED"])}, "hardware": hardware, "actuator": {"mode": "DRY_RUN_ONLY", "enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0}, "single_inference_per_frame": True, "one_nms_per_frame": True, "test_accessed": False}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", type=Path, required=True); parser.add_argument("--mode", choices=("legacy_reference", "dual"), required=True)
    args = parser.parse_args(); cfg = json.loads(args.config.read_text()); output = Path(cfg["output_dir"]); output.mkdir(parents=True, exist_ok=True)
    hardware = hardware_snapshot()
    if hardware["machine"] != "aarch64" or "Raspberry Pi 5 Model B Rev 1.0" not in (hardware["model"] or ""):
        raise SystemExit("PI_IDENTITY_FAIL")
    model_dir = Path(cfg["model_dir"])
    if sha256(model_dir / "model.ncnn.param") != cfg["param_sha256"] or sha256(model_dir / "model.ncnn.bin") != cfg["bin_sha256"]:
        raise SystemExit("DETECTOR_ARTIFACT_HASH_FAIL")
    detector = FrozenNcnnDetector(model_dir)
    if args.mode == "legacy_reference":
        count = capture_legacy_reference(detector, cfg, output)
        print(json.dumps({"status": "LEGACY_REFERENCE_CAPTURED", "frames": count}), flush=True)
        return 0
    parity = run_parity(detector, cfg, output)
    summary = run_dual(detector, cfg, output)
    summary["hardware"].update(hardware)
    summary["hardware"]["memory_after"] = meminfo(); summary["hardware"]["temperature_after"] = vcgencmd("measure_temp"); summary["hardware"]["throttling_after"] = vcgencmd("get_throttled")
    summary["parity_8"] = parity
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"status": summary["status"], "frames": summary["frames_processed"], "parity_8": parity["status"], "low_only": summary["stream_aggregates"]["low_only_frames"], "latency": summary["latency_ms"]["total_pipeline_ms"], "fps": summary["effective_fps"]}, indent=2), flush=True)
    return 0 if summary["status"] == "DRY_RUN_COMPLETE" and parity["status"] == "PARITY_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
