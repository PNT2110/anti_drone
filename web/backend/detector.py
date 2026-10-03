"""
web/backend/detector.py
High-performance YOLO detector wrapper optimized for CPU inference with
support for single-class drone ONNX models and multi-class COCO models.
"""

from __future__ import annotations

import threading
import time
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np
import ultralytics

try:
    from .tracker import IdentityTracker, create_tracker_from_env
except ImportError:
    from backend.tracker import IdentityTracker, create_tracker_from_env

try:
    import torch
except ImportError:  # pragma: no cover - ultralytics normally brings torch
    torch = None


@dataclass
class DetectionResult:
    """Detection results container returned by YOLODetector.detect()."""

    boxes: list[list[float]] = field(default_factory=list)  # [[x1, y1, x2, y2], ...]
    confidences: list[float] = field(default_factory=list)  # [0.94, 0.88, ...]
    class_ids: list[int] = field(default_factory=list)      # [0, 0, ...]
    class_names: list[str] = field(default_factory=list)    # ["drone", ...]
    track_ids: list[int | None] = field(default_factory=list)
    inference_time_ms: float = 0.0                          # Latency in milliseconds
    annotated_frame: np.ndarray = field(
        default_factory=lambda: np.zeros((0, 0, 3), dtype=np.uint8)
    )

    @property
    def total_detections(self) -> int:
        """Total number of objects detected."""
        return len(self.boxes)

    @property
    def avg_confidence(self) -> float:
        """Average confidence score across all detected objects."""
        if not self.confidences:
            return 0.0
        return float(np.mean(self.confidences))

    def to_dict(self) -> dict:
        """Serialize detection results to JSON-compatible dictionary."""
        return {
            "detections": [
                {
                    "box": [round(float(c), 2) for c in b],
                    "confidence": round(float(conf), 4),
                    "class_id": int(cid),
                    "label": cname,
                    "track_id": tid,
                }
                for b, conf, cid, cname, tid in zip(
                    self.boxes, self.confidences, self.class_ids, self.class_names,
                    self.track_ids or [None] * len(self.boxes),
                )
            ],
            "total_detections": self.total_detections,
            "avg_confidence": round(self.avg_confidence, 4),
            "inference_time_ms": round(self.inference_time_ms, 2),
            "track_ids": [tid for tid in self.track_ids if tid is not None],
        }


class FPSTracker:
    """Exponential Moving Average (EMA) FPS Tracker for jitter-free live display."""

    def __init__(self, alpha: float = 0.15):
        self.alpha = max(0.01, min(1.0, alpha))
        self.fps: float = 0.0
        self.last_time: Optional[float] = None
        self.frame_count: int = 0

    def update(self) -> float:
        """Update tracker with the current frame timestamp and return smoothed FPS."""
        now = time.perf_counter()
        if self.last_time is not None:
            dt = now - self.last_time
            if dt > 0.0:
                inst_fps = 1.0 / dt
                if self.fps == 0.0:
                    self.fps = inst_fps
                else:
                    self.fps = (1.0 - self.alpha) * self.fps + self.alpha * inst_fps
        self.last_time = now
        self.frame_count += 1
        return self.fps

    def reset(self) -> None:
        """Reset the FPS tracker state."""
        self.fps = 0.0
        self.last_time = None
        self.frame_count = 0


class YOLODetector:
    """
    Thread-safe YOLO inference engine wrapper optimized for CPU execution.
    Supports both single-class drone ONNX models ({0: 'drone'}) and 80-class COCO models.
    """

    # Thesis-Defense High-Contrast Color Palette (BGR)
    PALETTE = [
        (0, 230, 255),    # Vibrant Cyan / Electric Gold-Cyan (Primary Drone)
        (0, 255, 128),    # Neon Emerald Green
        (255, 140, 0),    # Deep Sky Blue
        (0, 165, 255),    # Vibrant Amber
        (255, 105, 180),  # Neon Pink
        (180, 105, 255),  # Electric Violet
        (50, 205, 50),    # Lime Green
        (0, 215, 255),    # Goldenrod
    ]

    def __init__(
        self,
        model_path: Union[str, Path],
        warmup: bool = True,
        device: Optional[str] = None,
    ):
        self.model_path = Path(model_path).resolve()
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file does not exist: {self.model_path}")

        requested_device = device or os.getenv("ANTI_DRONE_DEVICE", "auto")
        if requested_device.lower() == "auto":
            has_cuda = bool(torch is not None and torch.cuda.is_available())
            requested_device = "cuda:0" if has_cuda else "cpu"
        self.device = requested_device
        self.use_half = self.device.startswith("cuda") and os.getenv("ANTI_DRONE_HALF", "1") == "1"
        self._lock = threading.Lock()

        # Load model with explicit task='detect'
        self.model = ultralytics.YOLO(str(self.model_path), task="detect")

        # Normalize class names
        raw_names = self.model.names
        if isinstance(raw_names, dict):
            self.names: dict[int, str] = {int(k): str(v) for k, v in raw_names.items()}
        elif isinstance(raw_names, (list, tuple)):
            self.names = {i: str(n) for i, n in enumerate(raw_names)}
        else:
            self.names = {0: "drone"}

        # Check if single-class drone model
        self.is_drone_model: bool = (
            len(self.names) == 1 and "drone" in list(self.names.values())[0].lower()
        )

        self.fps_tracker = FPSTracker(alpha=0.15)
        self.identity_tracker = create_tracker_from_env()
        self._tracking_lock = threading.Lock()

        if warmup:
            self._warmup()

    def _warmup(self, size: tuple[int, int] = (480, 480)) -> None:
        """Run initial dummy inference to compile execution graph and prevent UI stutter."""
        dummy_frame = np.zeros((*size, 3), dtype=np.uint8)
        with self._lock:
            self.model.predict(
                source=dummy_frame,
                conf=0.25,
                iou=0.70,
                device=self.device,
                half=self.use_half,
                verbose=False,
            )

    def detect(
        self,
        frame: np.ndarray,
        conf: float = 0.25,
        iou: float = 0.70,
        draw: bool = True,
        draw_fps: bool = False,
        imgsz: Optional[int] = None,
        tracker: IdentityTracker | None = None,
        timestamp: float | None = None,
    ) -> DetectionResult:
        """
        Run object detection on an input BGR image frame.
        """
        if frame is None:
            raise ValueError("Input frame cannot be None")
        if not isinstance(frame, np.ndarray):
            raise TypeError(f"Expected numpy.ndarray, got {type(frame).__name__}")
        if frame.size == 0 or len(frame.shape) < 2:
            raise ValueError(f"Input frame is empty or invalid shape: {frame.shape}")

        # Ensure 3-channel BGR format
        if len(frame.shape) == 2:
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif len(frame.shape) == 3:
            if frame.shape[2] == 4:
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            elif frame.shape[2] == 3:
                frame_bgr = frame
            else:
                raise ValueError(f"Unsupported channel count: {frame.shape[2]}")
        else:
            raise ValueError(f"Unsupported image dimensions: {frame.shape}")

        conf_clamped = max(0.0, min(1.0, float(conf)))
        iou_clamped = max(0.0, min(1.0, float(iou)))

        t0 = time.perf_counter()
        with self._lock:
            results = self.model.predict(
                source=frame_bgr,
                conf=conf_clamped,
                iou=iou_clamped,
                device=self.device,
                half=self.use_half,
                imgsz=imgsz or 640,
                verbose=False,
            )
        inference_time_ms = (time.perf_counter() - t0) * 1000.0
        fps = self.fps_tracker.update()

        boxes: list[list[float]] = []
        confidences: list[float] = []
        class_ids: list[int] = []
        class_names: list[str] = []

        if results and len(results) > 0 and results[0].boxes is not None and len(results[0].boxes) > 0:
            r_boxes = results[0].boxes
            boxes = r_boxes.xyxy.cpu().numpy().tolist()
            confidences = r_boxes.conf.cpu().numpy().tolist()
            class_ids = r_boxes.cls.cpu().numpy().astype(int).tolist()
            class_names = [self.names.get(cid, f"class_{cid}") for cid in class_ids]

        tracker_timestamp = time.monotonic() if timestamp is None else float(timestamp)
        if tracker is None:
            with self._tracking_lock:
                track_ids = self.identity_tracker.update(
                    frame_bgr,
                    boxes,
                    confidences,
                    tracker_timestamp,
                )
        else:
            # Video tasks and camera sessions own their tracker instance. This
            # avoids cross-stream ID resets/interleaving through one detector.
            track_ids = tracker.update(frame_bgr, boxes, confidences, tracker_timestamp)

        annotated_frame = frame_bgr.copy()
        if draw:
            # Only boxes the tracker has confirmed are drawn; unconfirmed
            # ones are one-frame or low-confidence candidates.
            shown = [index for index, track_id in enumerate(track_ids) if track_id is not None]
            annotated_frame = self.draw_styled_detections(
                frame=annotated_frame,
                boxes=[boxes[index] for index in shown],
                confidences=[confidences[index] for index in shown],
                class_ids=[class_ids[index] for index in shown],
                class_names=[class_names[index] for index in shown],
                track_ids=[track_ids[index] for index in shown],
                fps=fps if draw_fps else None,
            )

        return DetectionResult(
            boxes=boxes,
            confidences=confidences,
            class_ids=class_ids,
            class_names=class_names,
            track_ids=track_ids,
            inference_time_ms=inference_time_ms,
            annotated_frame=annotated_frame,
        )

    def reset_tracking(self) -> None:
        """Start a fresh stream without reloading the neural model."""

        with self._tracking_lock:
            self.identity_tracker.reset()

    def draw_styled_detections(
        self,
        frame: np.ndarray,
        boxes: list[list[float]],
        confidences: list[float],
        class_ids: list[int],
        class_names: list[str],
        track_ids: list[int | None] | None = None,
        fps: Optional[float] = None,
    ) -> np.ndarray:
        """
        Render thesis-defense aesthetic bounding boxes, tactical corner brackets,
        and high-contrast confidence badges.
        """
        img = frame.copy()
        h, w = img.shape[:2]

        for index, ((x1, y1, x2, y2), conf, cid, cname) in enumerate(zip(
            boxes, confidences, class_ids, class_names
        )):
            track_id = track_ids[index] if track_ids and index < len(track_ids) else None
            ix1, iy1 = max(0, min(int(round(x1)), w - 1)), max(0, min(int(round(y1)), h - 1))
            ix2, iy2 = max(0, min(int(round(x2)), w - 1)), max(0, min(int(round(y2)), h - 1))
            if ix2 <= ix1 or iy2 <= iy1:
                continue

            color = (
                (0, 230, 255)
                if self.is_drone_model
                else self.PALETTE[cid % len(self.PALETTE)]
            )

            # 1. Main Bounding Box
            cv2.rectangle(img, (ix1, iy1), (ix2, iy2), color, 2, cv2.LINE_AA)

            # 2. Tactical Corner Accent Brackets
            clen = max(6, min(22, (ix2 - ix1) // 4, (iy2 - iy1) // 4))
            # Top-Left
            cv2.line(img, (ix1, iy1), (ix1 + clen, iy1), color, 3, cv2.LINE_AA)
            cv2.line(img, (ix1, iy1), (ix1, iy1 + clen), color, 3, cv2.LINE_AA)
            # Top-Right
            cv2.line(img, (ix2, iy1), (ix2 - clen, iy1), color, 3, cv2.LINE_AA)
            cv2.line(img, (ix2, iy1), (ix2, iy1 + clen), color, 3, cv2.LINE_AA)
            # Bottom-Left
            cv2.line(img, (ix1, iy2), (ix1 + clen, iy2), color, 3, cv2.LINE_AA)
            cv2.line(img, (ix1, iy2), (ix1, iy2 - clen), color, 3, cv2.LINE_AA)
            # Bottom-Right
            cv2.line(img, (ix2, iy2), (ix2 - clen, iy2), color, 3, cv2.LINE_AA)
            cv2.line(img, (ix2, iy2), (ix2, iy2 - clen), color, 3, cv2.LINE_AA)

            # 3. Confidence Badge & Label
            identity = f"ID {track_id}" if track_id is not None else "ID ?"
            label_text = f"{identity} · {cname.upper()} {conf * 100:.1f}%"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.52
            thickness = 1
            (tw, th), _ = cv2.getTextSize(label_text, font, font_scale, thickness)

            badge_y1 = max(0, iy1 - th - 8)
            badge_y2 = iy1
            badge_x1 = ix1
            badge_x2 = min(w, ix1 + tw + 10)

            # Filled badge background + high-contrast border
            cv2.rectangle(img, (badge_x1, badge_y1), (badge_x2, badge_y2), color, -1)
            cv2.rectangle(img, (badge_x1, badge_y1), (badge_x2, badge_y2), (20, 20, 20), 1)

            # Contrasting dark text
            cv2.putText(
                img,
                label_text,
                (badge_x1 + 5, badge_y2 - 4),
                font,
                font_scale,
                (10, 10, 10),
                thickness,
                cv2.LINE_AA,
            )

        # 4. Optional Live FPS Overlay
        if fps is not None and fps > 0:
            fps_str = f"FPS: {fps:.1f}"
            cv2.putText(
                img, fps_str, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 3, cv2.LINE_AA
            )
            cv2.putText(
                img, fps_str, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2, cv2.LINE_AA
            )

        return img

    def benchmark(
        self, iterations: int = 10, img_size: tuple[int, int] = (480, 640)
    ) -> dict:
        """
        Run inference latency and throughput benchmark on CPU.
        """
        dummy = np.zeros((*img_size, 3), dtype=np.uint8)
        latencies: list[float] = []

        for _ in range(iterations):
            t0 = time.perf_counter()
            with self._lock:
                self.model.predict(
                    source=dummy,
                    conf=0.25,
                    iou=0.70,
                    device=self.device,
                    verbose=False,
                )
            latencies.append((time.perf_counter() - t0) * 1000.0)

        lat_arr = np.array(latencies)
        mean_ms = float(np.mean(lat_arr))
        return {
            "model_path": str(self.model_path),
            "device": self.device,
            "iterations": iterations,
            "mean_ms": round(mean_ms, 2),
            "p95_ms": round(float(np.percentile(lat_arr, 95)), 2),
            "min_ms": round(float(np.min(lat_arr)), 2),
            "max_ms": round(float(np.max(lat_arr)), 2),
            "fps": round(1000.0 / mean_ms, 2) if mean_ms > 0 else 0.0,
        }
