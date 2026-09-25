#!/usr/bin/env python3
"""Run the fixed Scope 21 FP32 benchmark on a Raspberry Pi 5.

The runner is self-contained so the Pi does not need the source repository or
the 30k-image dataset.  It performs no TEST inference, tracking, camera I/O,
or quantization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np


CONF = 0.25
IOU = 0.70


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


def meminfo() -> dict:
    data = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in {"MemTotal", "MemAvailable", "MemFree"}:
            data[key] = int(value.split()[0]) * 1024
    return data


def vcgencmd(command: str) -> str | None:
    try:
        return subprocess.run(["vcgencmd", command], capture_output=True, text=True, timeout=3, check=False).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def letterbox(image: np.ndarray, size: int) -> tuple[np.ndarray, float, tuple[float, float]]:
    shape = image.shape[:2]
    r = min(size / shape[0], size / shape[1])
    new_unpad = (round(shape[1] * r), round(shape[0] * r))
    dw, dh = size - new_unpad[0], size - new_unpad[1]
    if shape[::-1] != new_unpad:
        image = cv2.resize(image, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = round(dh / 2 - 0.1), round(dh / 2 + 0.1)
    left, right = round(dw / 2 - 0.1), round(dw / 2 + 0.1)
    image = cv2.copyMakeBorder(image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
    return image, r, (dw / 2, dh / 2)


def preprocess(image: np.ndarray, size: int) -> tuple[np.ndarray, float, tuple[float, float]]:
    boxed, gain, pad = letterbox(image, size)
    rgb = cv2.cvtColor(boxed, cv2.COLOR_BGR2RGB)
    tensor = np.ascontiguousarray(rgb.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
    return tensor, gain, pad


def scale_box(box: list[float], gain: float, pad: tuple[float, float], shape: tuple[int, int]) -> list[float]:
    x1, y1, x2, y2 = box
    x1, x2 = (x1 - pad[0]) / gain, (x2 - pad[0]) / gain
    y1, y2 = (y1 - pad[1]) / gain, (y2 - pad[1]) / gain
    h, w = shape
    return [max(0.0, min(float(w), x1)), max(0.0, min(float(h), y1)), max(0.0, min(float(w), x2)), max(0.0, min(float(h), y2))]


def iou(a: list[float], b: list[float]) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    aa = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    bb = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = aa + bb - inter
    return inter / union if union else (1.0 if aa == bb == 0 else 0.0)


def nms(rows: list[dict]) -> list[dict]:
    ordered = sorted(rows, key=lambda x: x["confidence"], reverse=True)
    kept = []
    while ordered:
        current = ordered.pop(0)
        kept.append(current)
        ordered = [row for row in ordered if iou(current["bbox"], row["bbox"]) < IOU]
    return kept


def decode(raw: np.ndarray, gain: float, pad: tuple[float, float], image_shape: tuple[int, int]) -> tuple[list[dict], dict]:
    raw = np.asarray(raw, dtype=np.float32)
    if raw.ndim != 3:
        raise ValueError(f"unexpected raw rank: {raw.shape}")
    if raw.shape[1] == 5:
        candidates = raw[0].T
        rows = []
        for cx, cy, w, h, conf in candidates:
            if conf < CONF:
                continue
            box = [float(cx - w / 2), float(cy - h / 2), float(cx + w / 2), float(cy + h / 2)]
            rows.append({"class": 0, "confidence": float(conf), "bbox": scale_box(box, gain, pad, image_shape)})
        return nms(rows), {"raw_shape": list(raw.shape), "xywh": True, "nms_embedded": False, "nms_applications": 1, "candidate_count": int(candidates.shape[0])}
    if raw.shape[2] == 6:
        rows = []
        for x1, y1, x2, y2, conf, cls in raw[0]:
            if conf >= CONF:
                rows.append({"class": int(cls), "confidence": float(conf), "bbox": scale_box([float(x1), float(y1), float(x2), float(y2)], gain, pad, image_shape)})
        return rows, {"raw_shape": list(raw.shape), "xywh": False, "nms_embedded": True, "nms_applications": 0, "candidate_count": int(raw.shape[1])}
    raise ValueError(f"unknown output contract: {raw.shape}")


def load_runtime(candidate: dict):
    if candidate["backend"] == "onnx":
        import onnxruntime as ort
        session = ort.InferenceSession(str(Path(candidate["artifact_path"])), providers=["CPUExecutionProvider"], sess_options=ort.SessionOptions())
        session.set_providers(["CPUExecutionProvider"])
        return session, {"runtime": "onnxruntime", "version": ort.__version__, "threads": int(candidate["threads"])}
    import ncnn
    net = ncnn.Net()
    net.opt.use_vulkan_compute = False
    net.opt.num_threads = int(candidate["threads"])
    root = Path(candidate["artifact_path"])
    net.load_param(str(root / "model.ncnn.param"))
    net.load_model(str(root / "model.ncnn.bin"))
    return net, {"runtime": "ncnn", "version": getattr(ncnn, "__version__", "unknown"), "threads": int(candidate["threads"])}


def infer(runtime, candidate: dict, image: np.ndarray, size: int) -> tuple[list[dict], dict, dict]:
    tensor, gain, pad = preprocess(image, size)
    t0 = time.perf_counter()
    if candidate["backend"] == "onnx":
        input_name = runtime.get_inputs()[0].name
        outputs = runtime.run(None, {input_name: tensor})
        raw = np.asarray(outputs[0])
    else:
        import ncnn
        rgb_u8 = np.ascontiguousarray(np.clip(tensor[0].transpose(1, 2, 0) * 255.0, 0, 255).astype(np.uint8))
        mat = ncnn.Mat.from_pixels(rgb_u8, ncnn.Mat.PixelType.PIXEL_RGB, size, size)
        mat.substract_mean_normalize(np.zeros(3, dtype=np.float32), np.ones(3, dtype=np.float32) / 255.0)
        ex = runtime.create_extractor()
        ex.input("in0", mat)
        _, out = ex.extract("out0")
        raw = np.asarray(out)[None, ...]
    infer_ms = (time.perf_counter() - t0) * 1000.0
    p0 = time.perf_counter()
    detections, contract = decode(raw, gain, pad, image.shape[:2])
    post_ms = (time.perf_counter() - p0) * 1000.0
    return detections, contract, {"preprocess_ms": None, "inference_ms": infer_ms, "postprocess_ms": post_ms, "raw_dtype": str(raw.dtype)}


def compare(reference: list[dict], candidate: list[dict]) -> dict:
    result = {"status": "PARITY_PASS", "reference_count": len(reference), "candidate_count": len(candidate), "max_confidence_abs": 0.0, "min_bbox_iou": 1.0, "class_exact": True}
    if len(reference) != len(candidate):
        result["status"] = "PI_RUNTIME_PARITY_FAIL"
    for left, right in zip(reference, candidate):
        result["max_confidence_abs"] = max(result["max_confidence_abs"], abs(left["confidence"] - right["confidence"]))
        result["min_bbox_iou"] = min(result["min_bbox_iou"], iou(left["bbox"], right["bbox"]))
        result["class_exact"] = result["class_exact"] and left["class"] == right["class"]
    if result["max_confidence_abs"] > 0.05 or result["min_bbox_iou"] < 0.95 or not result["class_exact"]:
        result["status"] = "PI_RUNTIME_PARITY_FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    hardware = {"uname": platform.uname()._asdict(), "machine": platform.machine(), "model": Path("/proc/device-tree/model").read_text(errors="replace").strip("\x00\n") if Path("/proc/device-tree/model").exists() else None, "memory_before": meminfo(), "temperature_before": vcgencmd("measure_temp"), "throttling_before": vcgencmd("get_throttled")}
    if hardware["machine"] != "aarch64" or "Raspberry Pi 5" not in (hardware["model"] or ""):
        result = {"status": "RUNTIME_BLOCKED", "reason": "Pi identity check failed", "hardware": hardware, "results": []}
        (args.output / "benchmark_results.json").write_text(json.dumps(result, indent=2) + "\n")
        return 2
    reference = json.loads(Path(cfg["reference"]).read_text())
    reference_by_key = {(x["run_id"], x["image"]): x for x in reference["records"]}
    all_results = []
    for candidate in cfg["candidates"]:
        candidate_result = {"candidate_id": candidate["candidate_id"], "run_id": candidate["run_id"], "size": candidate["size"], "backend": candidate["backend"], "status": "PI_BENCHMARK_PASS", "artifact_hash_status": "PASS", "pi_parity": [], "load_time_ms": None, "preprocess_ms": [], "inference_ms": [], "postprocess_ms": [], "end_to_end_ms": [], "model_bytes": candidate["model_bytes"], "rss_idle_kb": rss_kb(), "rss_after_load_kb": None, "rss_peak_kb": None, "memory_before": meminfo(), "runtime": None, "warmup_passes": 20, "measured_passes": 100}
        expected = candidate["artifact_hashes"]
        for rel, digest in expected.items():
            actual = sha256(Path(candidate["artifact_path"]) / rel) if candidate["artifact_kind"] == "directory" else sha256(Path(candidate["artifact_path"]))
            if actual != digest:
                candidate_result["status"] = "ARTIFACT_HASH_FAIL"
                candidate_result["artifact_hash_status"] = "FAIL"
                candidate_result.setdefault("hash_errors", []).append({"relative": rel, "expected": digest, "actual": actual})
        if candidate_result["status"] != "PI_BENCHMARK_PASS":
            all_results.append(candidate_result)
            continue
        t0 = time.perf_counter()
        try:
            runtime, runtime_meta = load_runtime(candidate)
            candidate_result["load_time_ms"] = (time.perf_counter() - t0) * 1000.0
            candidate_result["runtime"] = runtime_meta
            candidate_result["rss_after_load_kb"] = rss_kb()
            parity_seen = set()
            for image_item in cfg["images"]:
                image = cv2.imread(str(Path(cfg["input_root"]) / image_item["filename"]))
                if image is None:
                    raise FileNotFoundError(image_item["filename"])
                for _ in range(20):
                    infer(runtime, candidate, image, candidate["size"])
                for _ in range(100):
                    t_all = time.perf_counter()
                    t_pre = time.perf_counter()
                    tensor, gain, pad = preprocess(image, candidate["size"])
                    pre_ms = (time.perf_counter() - t_pre) * 1000.0
                    t_inf = time.perf_counter()
                    if candidate["backend"] == "onnx":
                        raw = np.asarray(runtime.run(None, {runtime.get_inputs()[0].name: tensor})[0])
                    else:
                        import ncnn
                        rgb_u8 = np.ascontiguousarray(np.clip(tensor[0].transpose(1, 2, 0) * 255.0, 0, 255).astype(np.uint8))
                        mat = ncnn.Mat.from_pixels(rgb_u8, ncnn.Mat.PixelType.PIXEL_RGB, candidate["size"], candidate["size"])
                        mat.substract_mean_normalize(np.zeros(3, dtype=np.float32), np.ones(3, dtype=np.float32) / 255.0)
                        ex = runtime.create_extractor(); ex.input("in0", mat); _, out = ex.extract("out0"); raw = np.asarray(out)[None, ...]
                    inf_ms = (time.perf_counter() - t_inf) * 1000.0
                    t_post = time.perf_counter(); detections, contract = decode(raw, gain, pad, image.shape[:2]); post_ms = (time.perf_counter() - t_post) * 1000.0
                    candidate_result["preprocess_ms"].append(pre_ms); candidate_result["inference_ms"].append(inf_ms); candidate_result["postprocess_ms"].append(post_ms); candidate_result["end_to_end_ms"].append((time.perf_counter() - t_all) * 1000.0)
                    candidate_result["rss_peak_kb"] = max(candidate_result["rss_peak_kb"] or 0, rss_kb())
                    if image_item["filename"] not in parity_seen:
                        ref = reference_by_key[(candidate["run_id"], image_item["filename"])]
                        candidate_result["pi_parity"].append({"image": image_item["filename"], "contract": contract, "compare": compare(ref["detections"], detections)})
                        parity_seen.add(image_item["filename"])
            if any(x["compare"]["status"] != "PARITY_PASS" for x in candidate_result["pi_parity"]):
                candidate_result["status"] = "PI_RUNTIME_PARITY_FAIL"
        except Exception as exc:
            candidate_result["status"] = "RUNTIME_BLOCKED"
            candidate_result["error"] = repr(exc)
        all_results.append(candidate_result)
    hardware["memory_after"] = meminfo(); hardware["temperature_after"] = vcgencmd("measure_temp"); hardware["throttling_after"] = vcgencmd("get_throttled")
    result = {"status": "PASS" if all(x["status"] == "PI_BENCHMARK_PASS" for x in all_results) else "PARTIALLY_COMPLETE", "hardware": hardware, "protocol": {"warmup_passes_per_image": 20, "measured_passes_per_image": 100, "confidence": CONF, "nms_iou": IOU, "input_order": "fixed", "test_accessed": False}, "results": all_results}
    (args.output / "benchmark_results.json").write_text(json.dumps(result, indent=2) + "\n")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
