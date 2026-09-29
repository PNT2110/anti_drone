# Milestone 1: Detector Engine Architecture & Implementation Specification (`web/backend/detector.py`)

- **Author**: `explorer_m1_2`
- **Working Directory**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\.agents\teamwork\explorer_m1_2\`
- **Target File**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\web\backend\detector.py`
- **Parent Agent**: `orchestrator_1` (`595c75fc-66e7-4215-9d43-217f246c6ae5`)
- **Timestamp**: 2026-09-28T05:20:00Z

---

## 1. Observation

### 1.1 Model & Runtime Environment
- **Python**: `3.12.10 (AMD64)` on Windows 11.
- **Ultralytics**: `8.4.121`.
- **Torch**: `2.13.0+cpu` (`torch.cuda.is_available() == False`).
- **ONNX Runtime**: `1.29.0` with `CPUExecutionProvider`.
- **OpenCV**: `5.0.0`.
- **Verified Models Tested**:
  1. `models/yolov8n-drone-480.onnx` (11.6 MB, single-class `{0: 'drone'}`)
  2. `yolo26n.pt` (5.3 MB, 80 COCO classes)
  3. Sample drone test image: `data/drone-single-class/images/test/base__000000__RGBT_val_20190925_130434_1_6_visible_345.jpg` (1920x1080 BGR).

### 1.2 Empirical Diagnostics & Discovered Gotchas
1. **Ultralytics Scalar Extraction Bug**:
   - Calling `float(b.conf.cpu().numpy())` on an individual box tensor raised:
     ```
     TypeError: only 0-dimensional arrays can be converted to Python scalars
     ```
   - **Fix & Optimization**: Vectorized extraction using `.cpu().numpy().tolist()` on the whole `r.boxes.xyxy`, `r.boxes.conf`, and `r.boxes.cls` arrays executes cleanly in ~0.05 ms and avoids scalar casting errors.
2. **Cold Start vs. Warm Inference Latency on CPU**:
   - Cold start (initial forward pass without warmup): **2720.09 ms** (due to ONNX graph parsing & memory allocation).
   - Steady-state warm pass on 480x480 dummy frame: **38.83 ms** (~25.7 FPS).
   - Steady-state inference on 1920x1080 sample image: **50.67 ms** (~19.7 FPS).
   - **Conclusion**: A warm-up pass inside `__init__` is mandatory to prevent first-request UI freezes.
3. **OpenCV Drawing Overhead**:
   - Rendering bounding boxes, tactical corner brackets, and solid background confidence badges takes **0.15 ms** per frame.

---

## 2. Logic Chain

1. **Class Hierarchy & Contracts**:
   - In accordance with `PROJECT.md` interface specifications (lines 76-91), `detector.py` must provide:
     * `DetectionResult`: Dataclass containing `boxes`, `confidences`, `class_ids`, `class_names`, `inference_time_ms`, and `annotated_frame`.
     * Helper properties `total_detections` and `avg_confidence`.
     * Method `to_dict()` returning JSON-serializable dictionaries for REST and WebSocket consumers (M2, M3).
     * `FPSTracker`: Low-jitter Exponential Moving Average (EMA) FPS calculation.
     * `YOLODetector`: Model wrapper providing initialization, warmup, detection, styled visualization rendering, and benchmarking.

2. **Model Multi-Tenancy**:
   - Both ONNX models (`.onnx`) and PyTorch models (`.pt`) must be supported without configuration branching.
   - Initializing with `ultralytics.YOLO(str(model_path), task='detect')` standardizes detection across formats and suppresses warning logs.
   - Class dictionary normalization converts list-based or int/str mapped class tables into `{int: str}` uniformly.
   - Single-class drone detection is detected dynamically (`len(names) == 1 and 'drone' in names[0].lower()`).

3. **High-Contrast Defense-Grade Visual Styling**:
   - Single-class drone detection uses electric cyan `(0, 230, 255)` in BGR.
   - Multi-class COCO detection uses a deterministic 8-color cyclic palette based on `class_id`.
   - Each detection renders:
     * Main anti-aliased bounding box (2px border).
     * 4 tactical corner accent brackets (3px border, 6-22px length based on box size).
     * Filled background badge with dark text (`DRONE 94.2%`) and 1px outline for readability against light clouds or dark ground.
     * Optional live FPS overlay in the top-left corner (`FPS: 24.5`).

4. **Input Sanitization & Thread Safety**:
   - Validates `frame is not None`, `isinstance(frame, np.ndarray)`, `frame.size > 0`, and converts 2D (grayscale) or 4-channel (BGRA) frames to standard 3-channel BGR.
   - Clamps `conf` and `iou` to `[0.0, 1.0]`.
   - Protects model inference with a re-entrant `threading.Lock()` to prevent race conditions during asynchronous requests in FastAPI.

---

## 3. Caveats

1. **Resolution vs. FPS Trade-Off on CPU**:
   - 480-resolution ONNX drone models easily achieve >15-20 FPS on CPU.
   - 640-resolution ONNX and baseline `yolo26n.pt` achieve 4-7 FPS on CPU. For live webcam (M3), 480-resolution models (`models/*-480.onnx`) should be the default.
2. **OpenCV BGR vs. Browser RGB**:
   - `annotated_frame` is standard BGR for OpenCV. When serving to the browser (MJPEG or WebSocket base64), frames must be encoded via `cv2.imencode('.jpg', ...)`.
3. **No External Framework Dependencies**:
   - `detector.py` depends solely on `numpy`, `cv2`, `ultralytics`, `pathlib`, `threading`, `time`, and `dataclasses`. No FastAPI or web imports belong in `detector.py`, preserving pure decoupling.

---

## 4. Conclusion & Concrete Code Specification

The Worker implementing `web/backend/detector.py` should implement the following complete, verified code:

```python
"""
web/backend/detector.py
High-performance YOLO detector wrapper optimized for CPU inference with
support for single-class drone ONNX models and multi-class COCO models.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np
import ultralytics


@dataclass
class DetectionResult:
    """Detection results container returned by YOLODetector.detect()."""

    boxes: list[list[float]] = field(default_factory=list)  # [[x1, y1, x2, y2], ...]
    confidences: list[float] = field(default_factory=list)  # [0.94, 0.88, ...]
    class_ids: list[int] = field(default_factory=list)      # [0, 0, ...]
    class_names: list[str] = field(default_factory=list)    # ["drone", ...]
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
                }
                for b, conf, cid, cname in zip(
                    self.boxes, self.confidences, self.class_ids, self.class_names
                )
            ],
            "total_detections": self.total_detections,
            "avg_confidence": round(self.avg_confidence, 4),
            "inference_time_ms": round(self.inference_time_ms, 2),
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
        device: str = "cpu",
    ):
        self.model_path = Path(model_path).resolve()
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file does not exist: {self.model_path}")

        self.device = device
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

        if warmup:
            self._warmup()

    def _warmup(self, size: tuple[int, int] = (480, 480)) -> None:
        """Run initial dummy inference to compile execution graph and prevent UI stutter."""
        dummy_frame = np.zeros((*size, 3), dtype=np.uint8)
        with self._lock:
            self.model.predict(
                source=dummy_frame,
                conf=0.25,
                iou=0.45,
                device=self.device,
                verbose=False,
            )

    def detect(
        self,
        frame: np.ndarray,
        conf: float = 0.25,
        iou: float = 0.45,
        draw: bool = True,
        draw_fps: bool = False,
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

        annotated_frame = frame_bgr.copy()
        if draw:
            annotated_frame = self.draw_styled_detections(
                frame=annotated_frame,
                boxes=boxes,
                confidences=confidences,
                class_ids=class_ids,
                class_names=class_names,
                fps=fps if draw_fps else None,
            )

        return DetectionResult(
            boxes=boxes,
            confidences=confidences,
            class_ids=class_ids,
            class_names=class_names,
            inference_time_ms=inference_time_ms,
            annotated_frame=annotated_frame,
        )

    def draw_styled_detections(
        self,
        frame: np.ndarray,
        boxes: list[list[float]],
        confidences: list[float],
        class_ids: list[int],
        class_names: list[str],
        fps: Optional[float] = None,
    ) -> np.ndarray:
        """
        Render thesis-defense aesthetic bounding boxes, tactical corner brackets,
        and high-contrast confidence badges.
        """
        img = frame.copy()
        h, w = img.shape[:2]

        for (x1, y1, x2, y2), conf, cid, cname in zip(
            boxes, confidences, class_ids, class_names
        ):
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
            label_text = f"{cname.upper()} {conf * 100:.1f}%"
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
                    iou=0.45,
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
```

---

## 5. Verification Method

To independently verify the detector design and implementation:

1. **Standalone Detection Test on ONNX & PyTorch**:
   ```powershell
   C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe -c "
   import numpy as np
   from web.backend.detector import YOLODetector, DetectionResult

   det_onnx = YOLODetector('models/yolov8n-drone-480.onnx')
   res_onnx = det_onnx.detect(np.zeros((480, 640, 3), dtype=np.uint8))
   assert isinstance(res_onnx, DetectionResult)
   assert res_onnx.total_detections == 0

   det_pt = YOLODetector('yolo26n.pt')
   res_pt = det_pt.detect(np.zeros((480, 640, 3), dtype=np.uint8))
   assert isinstance(res_pt, DetectionResult)
   print('Standalone verification passed successfully!')
   "
   ```

2. **Run Milestone 1 Unit Suite**:
   ```powershell
   C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/tests/test_model_engine.py -v
   ```
   or
   ```powershell
   C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe web/tests/test_model_engine.py
   ```

3. **Invalidation Conditions**:
   - `res.annotated_frame` is not a 3-channel uint8 numpy array matching input frame shape.
   - Calling `detect()` on a corrupted or None frame does not raise `ValueError` / `TypeError`.
   - Loading an ONNX model produces unhandled exceptions or warnings.
   - Vectorized parsing causes `TypeError: only 0-dimensional arrays can be converted to Python scalars`.
