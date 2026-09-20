"""Small CPU runtime used by the Phase 5 Pi pipeline.

The module intentionally keeps the Pi dependency surface small: OpenCV,
NumPy, and one selected inference backend.  Training, Ultralytics and CUDA are
not imported here.
"""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass
class Detection:
    box: np.ndarray
    confidence: float
    class_id: int = 0


@dataclass
class Track:
    track_id: int
    box: np.ndarray
    confidence: float
    hits: int = 1
    missed: int = 0
    last_frame: int = 0


def letterbox(image: np.ndarray, size: int = 640, color: tuple[int, int, int] = (114, 114, 114)) -> tuple[np.ndarray, float, tuple[float, float]]:
    height, width = image.shape[:2]
    scale = min(size / width, size / height)
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    pad_x = (size - resized_width) / 2
    pad_y = (size - resized_height) / 2
    output = np.full((size, size, 3), color, dtype=np.uint8)
    left, top = round(pad_x - 0.1), round(pad_y - 0.1)
    output[top : top + resized_height, left : left + resized_width] = resized
    return output, scale, (pad_x, pad_y)


def preprocess(image: np.ndarray, size: int = 640) -> tuple[np.ndarray, float, tuple[float, float]]:
    canvas, scale, pad = letterbox(image, size)
    # Camera/OpenCV frames are BGR; the model contract is RGB, float32, 0..1.
    tensor = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return tensor[None, ...], scale, pad


def box_iou(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, float(a[2] - a[0])) * max(0.0, float(a[3] - a[1]))
    area_b = max(0.0, float(b[2] - b[0])) * max(0.0, float(b[3] - b[1]))
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def decode_yolo_output(raw: Any, original_shape: tuple[int, int], scale: float, pad: tuple[float, float], confidence: float = 0.25, nms_iou: float = 0.70) -> list[Detection]:
    """Decode the raw one-class YOLO export and restore original-image boxes."""
    output = np.asarray(raw)
    output = np.squeeze(output)
    if output.ndim == 1 and output.size >= 5:
        output = output.reshape(1, -1)
    if output.ndim != 2:
        raise ValueError(f"Unsupported model output shape: {output.shape}")
    # This project has one class, so exported channel-first output is exactly
    # (5, N); keep the already-decoded (1, 5) case untouched.
    if output.shape[0] == 5 and output.shape[1] != 5:
        output = output.T
    if output.shape[1] < 5:
        raise ValueError(f"Output needs xywh plus score, got {output.shape}")
    boxes_xywh = output[:, :4].astype(np.float32)
    class_scores = output[:, 4:].astype(np.float32)
    class_ids = np.argmax(class_scores, axis=1)
    scores = class_scores[np.arange(len(class_scores)), class_ids]
    keep = scores >= confidence
    boxes_xywh, scores, class_ids = boxes_xywh[keep], scores[keep], class_ids[keep]
    if not len(scores):
        return []
    xyxy = np.column_stack(
        (
            boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2,
            boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2,
            boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2,
            boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2,
        )
    )
    selected = cv2.dnn.NMSBoxes(xyxy.tolist(), scores.tolist(), float(confidence), float(nms_iou))
    indices = np.asarray(selected).reshape(-1).astype(int) if len(selected) else np.empty(0, dtype=int)
    height, width = original_shape
    pad_x, pad_y = pad
    detections: list[Detection] = []
    for index in indices:
        box = xyxy[index].copy()
        box[[0, 2]] = (box[[0, 2]] - pad_x) / scale
        box[[1, 3]] = (box[[1, 3]] - pad_y) / scale
        box[[0, 2]] = np.clip(box[[0, 2]], 0, width)
        box[[1, 3]] = np.clip(box[[1, 3]], 0, height)
        detections.append(Detection(box=box, confidence=float(scores[index]), class_id=int(class_ids[index])))
    return detections


class OnnxEngine:
    def __init__(self, model_path: Path):
        ort = importlib.import_module("onnxruntime")
        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def infer(self, tensor: np.ndarray) -> list[np.ndarray]:
        return self.session.run(None, {self.input_name: tensor})


class NcnnEngine:
    def __init__(self, model_dir: Path):
        ncnn = importlib.import_module("ncnn")
        self.ncnn = ncnn
        self.net = ncnn.Net()
        self.net.load_param(str(model_dir / "model.ncnn.param"))
        self.net.load_model(str(model_dir / "model.ncnn.bin"))

    def infer(self, tensor: np.ndarray) -> list[np.ndarray]:
        # ncnn expects a HWC RGB image; tensor is already RGB/normalized BCHW.
        image = np.clip(tensor[0].transpose(1, 2, 0) * 255.0, 0, 255).astype(np.uint8)
        mat = self.ncnn.Mat.from_pixels(image, self.ncnn.Mat.PixelType.PIXEL_RGB, image.shape[1], image.shape[0])
        mat.substract_mean_normalize([], [1 / 255.0, 1 / 255.0, 1 / 255.0])
        extractor = self.net.create_extractor()
        extractor.input("in0", mat)
        status, output = extractor.extract("out0")
        if status != 0:
            raise RuntimeError(f"NCNN inference failed with status {status}")
        return [np.asarray(output)]


class LiteRTEngine:
    def __init__(self, model_path: Path):
        interpreter_cls = None
        for module_name in ("tflite_runtime.interpreter", "ai_edge_litert.interpreter", "tensorflow.lite"):
            try:
                interpreter_cls = getattr(importlib.import_module(module_name), "Interpreter")
                break
            except (ImportError, AttributeError):
                continue
        if interpreter_cls is None:
            raise RuntimeError("No TFLite interpreter installed")
        self.interpreter = interpreter_cls(model_path=str(model_path), num_threads=4)
        self.interpreter.allocate_tensors()
        self.input = self.interpreter.get_input_details()[0]
        self.outputs = self.interpreter.get_output_details()
        self.nhwc = self.input["shape"][-1] == 3
        # The Phase 4 ONNX->TFLite bridge stores xywh in [0, 1] to match the
        # LiteRT/Ultralytics legacy contract.  DetectorPipeline converts it
        # back to input-pixel coordinates before letterbox restoration.
        self.normalized_output = True

    def infer(self, tensor: np.ndarray) -> list[np.ndarray]:
        value = tensor
        if self.nhwc:
            value = value.transpose(0, 2, 3, 1)
        if self.input["dtype"] != np.float32:
            scale, zero = self.input["quantization"]
            value = np.round(tensor / scale + zero).astype(self.input["dtype"])
        self.interpreter.set_tensor(self.input["index"], value)
        self.interpreter.invoke()
        return [self.interpreter.get_tensor(item["index"]) for item in self.outputs]


def make_engine(runtime: str, model: Path) -> Any:
    if runtime == "onnx":
        return OnnxEngine(model)
    if runtime == "ncnn":
        return NcnnEngine(model)
    if runtime in {"tflite", "litert"}:
        return LiteRTEngine(model)
    raise ValueError(f"Unknown runtime: {runtime}")


class ByteTrackLite:
    """Bounded IoU tracker with ByteTrack-style high/low confidence passes."""

    def __init__(self, high_threshold: float = 0.25, low_threshold: float = 0.10, match_iou: float = 0.30, max_lost: int = 15):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.match_iou = match_iou
        self.max_lost = max_lost
        self.next_id = 1
        self.tracks: dict[int, Track] = {}

    def update(self, detections: list[Detection], frame_id: int) -> list[Track]:
        candidates = [d for d in detections if d.confidence >= self.low_threshold]
        unmatched = set(range(len(candidates)))
        for track in list(self.tracks.values()):
            best_index, best_iou = -1, 0.0
            for index in unmatched:
                overlap = box_iou(track.box, candidates[index].box)
                if overlap > best_iou:
                    best_index, best_iou = index, overlap
            if best_index >= 0 and best_iou >= self.match_iou:
                detection = candidates[best_index]
                track.box = detection.box
                track.confidence = detection.confidence
                track.hits += 1
                track.missed = 0
                track.last_frame = frame_id
                unmatched.remove(best_index)
            else:
                track.missed += 1
        for index in unmatched:
            detection = candidates[index]
            if detection.confidence >= self.high_threshold:
                self.tracks[self.next_id] = Track(self.next_id, detection.box, detection.confidence, last_frame=frame_id)
                self.next_id += 1
        self.tracks = {key: value for key, value in self.tracks.items() if value.missed <= self.max_lost}
        return list(self.tracks.values())


class AlertState:
    def __init__(self, confirm_hits: int = 3, confirm_window: int = 5, cooldown_frames: int = 30):
        self.confirm_hits = confirm_hits
        self.confirm_window = confirm_window
        self.cooldown_frames = cooldown_frames
        self.history: dict[int, list[int]] = {}
        self.last_alert = -10**9

    def update(self, tracks: list[Track], frame_id: int) -> list[Track]:
        alerts: list[Track] = []
        for track in tracks:
            history = [frame for frame in self.history.get(track.track_id, []) if frame >= frame_id - self.confirm_window + 1]
            history.append(frame_id)
            self.history[track.track_id] = history
            if len(history) >= self.confirm_hits and frame_id - self.last_alert >= self.cooldown_frames:
                alerts.append(track)
                self.last_alert = frame_id
        self.history = {key: value for key, value in self.history.items() if value and frame_id - value[-1] <= self.confirm_window * 2}
        return alerts


class DetectorPipeline:
    def __init__(self, runtime: str, model: Path, imgsz: int = 640, confidence: float = 0.25, nms_iou: float = 0.70):
        self.engine = make_engine(runtime, model)
        self.imgsz = imgsz
        self.confidence = confidence
        self.nms_iou = nms_iou
        self.tracker = ByteTrackLite(high_threshold=confidence)
        self.alerts = AlertState()

    def process(self, frame: np.ndarray, frame_id: int) -> tuple[np.ndarray, list[Track], list[Track], float]:
        started = time.perf_counter()
        tensor, scale, pad = preprocess(frame, self.imgsz)
        raw = self.engine.infer(tensor)
        if getattr(self.engine, "normalized_output", False):
            normalized = np.asarray(raw[0]).copy()
            if normalized.ndim == 3 and normalized.shape[1] == 5:
                normalized[:, :4, :] *= self.imgsz
            elif normalized.ndim == 3 and normalized.shape[-1] >= 5:
                normalized[..., :4] *= self.imgsz
            raw[0] = normalized
        detections = decode_yolo_output(raw[0], frame.shape[:2], scale, pad, self.confidence, self.nms_iou)
        tracks = self.tracker.update(detections, frame_id)
        alerts = self.alerts.update(tracks, frame_id)
        latency_ms = (time.perf_counter() - started) * 1000
        output = frame.copy()
        for track in tracks:
            x1, y1, x2, y2 = map(int, track.box)
            color = (0, 0, 255) if track in alerts else (0, 220, 0)
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            cv2.putText(output, f"drone id={track.track_id} {track.confidence:.2f}", (x1, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        cv2.putText(output, f"latency={latency_ms:.1f}ms tracks={len(tracks)}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 0), 2)
        return output, tracks, alerts, latency_ms
