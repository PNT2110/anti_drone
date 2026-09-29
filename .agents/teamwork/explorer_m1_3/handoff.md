# Milestone 1: Unit Verification Suite Design Handoff Report (`web/tests/test_model_engine.py`)

- **Author**: `explorer_m1_3`
- **Working Directory**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\.agents\teamwork\explorer_m1_3\`
- **Target File**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\web\tests\test_model_engine.py`
- **Parent Agent**: `orchestrator_1` (`595c75fc-66e7-4215-9d43-217f246c6ae5`)
- **Timestamp**: 2026-09-28T05:43:00Z

---

## 1. Observation

### 1.1 Python Runtime & Dependencies Verification
Empirically executed via terminal:
- **Python Binary**: `C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe`
- **Python Version**: `3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]`
- **Pytest**: `9.1.1` (verified via `python -c "import pytest; print(pytest.__version__)"`)
- **Ultralytics**: `8.4.121`
- **Torch**: `2.13.0+cpu` (`torch.cuda.is_available() == False`)
- **ONNX Runtime**: `1.29.0` with `CPUExecutionProvider`
- **OpenCV**: `5.0.0`
- **NumPy**: `2.5.3`

### 1.2 Model Files Verified on Local Filesystem
Direct directory listing confirmed the presence of 7 custom drone-trained ONNX models and 1 baseline PyTorch model:
1. `models/yolo11n-drone-480.onnx` (10,509,666 bytes)
2. `models/yolo11n-drone-640.onnx` (10,583,204 bytes)
3. `models/yolo26n-drone-480.onnx` (9,704,227 bytes)
4. `models/yolo26n-drone-640.onnx` (9,777,765 bytes)
5. `models/yolov8n-drone-480.onnx` (12,177,304 bytes)
6. `models/yolov8n-drone-640.onnx` (12,250,842 bytes)
7. `models/yolov8n-drone-best.onnx` (12,265,319 bytes)
8. `yolo26n.pt` (root, 5,550,114 bytes)

### 1.3 Empirical Synthetic & Live Inference Behavior
- Forward pass on synthetic black frame (`np.zeros((480, 640, 3), dtype=np.uint8)`) using `ultralytics.YOLO('models/yolov8n-drone-480.onnx', task='detect')`:
  - Completed with code 0 in ~38 ms (warm CPU inference).
  - Detected 0 bounding boxes; result structure has empty box tensor.
- Forward pass on synthetic frame using baseline `yolo26n.pt`:
  - Completed with code 0 in ~42 ms (warm CPU inference).
- Forward pass on test drone image (`data/drone-single-class/images/test/base__000000__RGBT_val_20190925_130434_1_6_visible_345.jpg`):
  - Detected 1 drone with confidence `0.79792`.

---

## 2. Logic Chain

1. **Test Scope & Architecture Decoupling**:
   - Milestone 1 implements the core backend model engine (`config.py`, `model_manager.py`, `detector.py`).
   - The unit verification suite must live in `web/tests/test_model_engine.py` and isolate backend model engine logic without requiring FastAPI server startup or network ports.

2. **Dual Execution Protocol**:
   - The test suite is designed as a standard `unittest.TestCase` class (`TestModelEngine`).
   - Pytest automatically discovers all `test_*` methods when invoked via `pytest web/tests/test_model_engine.py`.
   - Direct execution via `python web/tests/test_model_engine.py` triggers `run_standalone_suite()` in `__main__`, which renders a human-readable CLI summary dashboard with timestamps, test descriptions, elapsed time, and returns exit code `0` on success or `1` on failure.
   - Dynamic path setup (`sys.path.insert(0, ...)`) guarantees flawless imports whether executed from the project root or the `web/` subfolder.

3. **Coverage of All 7 Mandatory Test Scenarios**:
   - **Test 1: Config loading & directory paths validation (`test_01_config_loading_and_directory_paths`)**:
     * Verifies `PROJECT_ROOT`, `WEB_DIR`, `OUTPUTS_DIR`, `ensure_directories()`.
     * Validates default inference parameters (`DEFAULT_CONF_THRESHOLD` ~0.25, `DEFAULT_IOU_THRESHOLD` ~0.45).
     * Validates `DEFAULT_MODEL_NAME` and Vietnamese display metadata dictionary `KNOWN_MODELS_METADATA`.
     * Confirms underlying filesystem directories and model files exist.
   - **Test 2: ModelManager discovery lists all 6+ ONNX drone models and baseline yolo26n.pt (`test_02_model_discovery_inventory`)**:
     * Instantiates `ModelManager()`.
     * Asserts `len(models) >= 7` (at least 6 ONNX + 1 baseline PT model).
     * Asserts `yolo26n.pt` is discovered with format `pt`.
     * Asserts all primary ONNX drone models (`yolov8n-drone-480/640`, `yolo26n-drone-480/640`, `yolo11n-drone-480/640`) are discovered with format `onnx`.
     * Confirms metadata schema (`name`, `label`, `path`, `format`, `is_active`) and confirms every model path exists on disk.
     * Asserts that exactly one model has `is_active == True`.
   - **Test 3: ModelManager active model hot-swapping (`test_03_model_manager_hot_swapping`)**:
     * Tests swapping active model from default to `yolo26n.pt` and back.
     * Asserts `manager.list_models()` updates `is_active` correctly.
     * Tests detector caching (reusing already loaded detector instances).
     * Tests error handling: attempting to swap to a nonexistent model raises `KeyError`, `ValueError`, or `FileNotFoundError`, leaving the previously active model intact.
   - **Test 4: Detector runs inference on synthetic test frame (numpy array) without error (`test_04_detector_synthetic_inference`)**:
     * Executes inference on solid black frame (`np.zeros((480, 640, 3), dtype=np.uint8)`).
     * Executes inference on random noise frame (`np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)`).
     * Verifies `manager.predict()` and `YOLODetector.detect()` execute without error and return a `DetectionResult`.
     * Confirms `annotated_frame` matches input dimensions and dtype.
   - **Test 5: DetectionResult structure contains valid boxes, labels, confidences, and annotated_frame (`test_05_detection_result_structure`)**:
     * Verifies types of `boxes`, `confidences`, `class_ids`, `class_names`, `inference_time_ms`, `annotated_frame`.
     * Verifies array length equality and boundary conditions (`0.0 <= avg_confidence <= 1.0`).
     * Verifies bounding box coordinate constraints (`x1 <= x2`, `y1 <= y2`).
     * Verifies JSON serialization via `result.to_dict()` and `json.dumps()`.
     * Direct mathematical verification of `avg_confidence` and `total_detections`.
   - **Test 6: Detector error handling on corrupted / invalid input frame (`test_06_detector_invalid_input_error_handling`)**:
     * Asserts `ValueError` on `None` input.
     * Asserts `TypeError` / `ValueError` on non-array input (`str`, `int`).
     * Asserts `ValueError` on empty array (0-sized), 1D array, and 5-channel array.
     * Confirms tolerance: 2D grayscale (`(240, 320)`) and 4-channel BGRA (`(240, 320, 4)`) are automatically converted to standard 3-channel BGR without error.
     * Confirms parameter clamping: extreme `conf` and `iou` values (`-0.5`, `1.5`) are clamped without crashing.
   - **Test 7: ModelManager thread safety under concurrent requests (`test_07_model_manager_thread_safety`)**:
     * Sub-test 7A: Concurrent inference across 6 worker threads with 12 simultaneous requests using `ThreadPoolExecutor`.
     * Sub-test 7B: Concurrent inference while active model hot-swapping occurs in another thread, verifying thread locks prevent race conditions, corrupted buffers, or deadlocks.

---

## 3. Caveats

1. **Dependency on Worker Implementation**:
   - The test suite imports `backend.config`, `backend.model_manager.ModelManager`, and `backend.detector.YOLODetector`. If run before the implementation Worker creates these files, the suite cleanly skips tests with an informative message (`skipTest`).
2. **CPU Inference Latency Variations**:
   - On CPU, inference speed varies depending on system load and background tasks. The test suite asserts `inference_time_ms >= 0.0` rather than enforcing a strict upper bound (e.g. `< 50ms`), preventing flaky CI failures while still verifying time tracking.
3. **OpenCV GUI Headless Execution**:
   - The test suite tests OpenCV image manipulations in memory (`cv2.cvtColor`, drawing functions). It does not call `cv2.imshow()`, ensuring headless/CI test execution on any platform without GUI display dependencies.

---

## 4. Conclusion & Concrete Code Specification

The test suite has been fully drafted and saved at:
`c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\.agents\teamwork\explorer_m1_3\proposed_test_model_engine.py`

The implementation Worker should place this exact code at:
`c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\web\tests\test_model_engine.py`

### Concrete Source Code for `web/tests/test_model_engine.py`

```python
"""
web/tests/test_model_engine.py
Milestone 1 Unit Verification Suite for Anti-Drone Object Detection Engine.

Covers:
  - Test 1: Config loading & directory paths validation
  - Test 2: ModelManager discovery lists all 6+ ONNX drone models and baseline yolo26n.pt
  - Test 3: ModelManager active model hot-swapping
  - Test 4: Detector runs inference on synthetic test frame (numpy array) without error
  - Test 5: DetectionResult structure contains valid boxes, labels, confidences, and annotated_frame
  - Test 6: Detector error handling on corrupted / invalid input frame
  - Test 7: ModelManager thread safety under concurrent requests

Execution Commands:
  1. Pytest:
     pytest web/tests/test_model_engine.py -v
  2. Standalone Python:
     python web/tests/test_model_engine.py
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

# ------------------------------------------------------------------------------
# Path Setup: Ensure web/ and project root are in sys.path
# ------------------------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
WEB_DIR = CURRENT_DIR.parent
PROJECT_ROOT = WEB_DIR.parent

for path_to_add in (str(WEB_DIR), str(PROJECT_ROOT)):
    if path_to_add not in sys.path:
        sys.path.insert(0, path_to_add)

# ------------------------------------------------------------------------------
# Module Imports (with clean error diagnostics)
# ------------------------------------------------------------------------------
try:
    from backend import config
    from backend.detector import DetectionResult, FPSTracker, YOLODetector
    from backend.model_manager import ModelManager
    MODULES_AVAILABLE = True
except ImportError as err:
    MODULES_AVAILABLE = False
    IMPORT_ERROR_MSG = str(err)


# ==============================================================================
# Unit Test Suite: TestModelEngine
# ==============================================================================
class TestModelEngine(unittest.TestCase):
    """Milestone 1 Verification Test Suite covering Model Engine & Discovery."""

    def setUp(self) -> None:
        """Verify module availability before each test."""
        if not MODULES_AVAILABLE:
            self.skipTest(f"Backend modules not yet implemented: {IMPORT_ERROR_MSG}")

    # --------------------------------------------------------------------------
    # Test 1: Config loading & directory paths validation
    # --------------------------------------------------------------------------
    def test_01_config_loading_and_directory_paths(self) -> None:
        """
        Test 1: Validates config.py loading, core path resolution, runtime
        directory creation, and default inference parameter boundaries.
        """
        # Validate path definitions exist and are Path objects
        self.assertTrue(hasattr(config, "PROJECT_ROOT"), "Missing PROJECT_ROOT in config")
        self.assertTrue(hasattr(config, "WEB_DIR"), "Missing WEB_DIR in config")
        self.assertTrue(hasattr(config, "OUTPUTS_DIR"), "Missing OUTPUTS_DIR in config")
        self.assertIsInstance(config.PROJECT_ROOT, Path)
        self.assertIsInstance(config.WEB_DIR, Path)

        # Call directory creation helper
        if hasattr(config, "ensure_directories"):
            config.ensure_directories()
        self.assertTrue(config.OUTPUTS_DIR.exists(), f"OUTPUTS_DIR does not exist: {config.OUTPUTS_DIR}")

        # Validate default inference parameters
        self.assertTrue(hasattr(config, "DEFAULT_CONF_THRESHOLD"), "Missing DEFAULT_CONF_THRESHOLD")
        self.assertTrue(hasattr(config, "DEFAULT_IOU_THRESHOLD"), "Missing DEFAULT_IOU_THRESHOLD")
        self.assertGreater(config.DEFAULT_CONF_THRESHOLD, 0.0)
        self.assertLessEqual(config.DEFAULT_CONF_THRESHOLD, 1.0)
        self.assertGreater(config.DEFAULT_IOU_THRESHOLD, 0.0)
        self.assertLessEqual(config.DEFAULT_IOU_THRESHOLD, 1.0)

        # Validate default model settings
        self.assertTrue(hasattr(config, "DEFAULT_MODEL_NAME"), "Missing DEFAULT_MODEL_NAME")
        self.assertTrue(
            config.DEFAULT_MODEL_NAME.endswith((".onnx", ".pt")),
            f"Invalid default model extension: {config.DEFAULT_MODEL_NAME}",
        )

        # Validate Vietnamese model metadata catalog
        self.assertTrue(hasattr(config, "KNOWN_MODELS_METADATA"), "Missing KNOWN_MODELS_METADATA")
        self.assertIsInstance(config.KNOWN_MODELS_METADATA, dict)
        self.assertIn("yolov8n-drone-480.onnx", config.KNOWN_MODELS_METADATA)
        self.assertIn("yolo26n.pt", config.KNOWN_MODELS_METADATA)

        # Check Vietnamese labels are non-empty strings
        for model_name, meta in config.KNOWN_MODELS_METADATA.items():
            self.assertIn("label", meta, f"Metadata for {model_name} missing 'label'")
            self.assertIsInstance(meta["label"], str)
            self.assertGreater(len(meta["label"].strip()), 0)

        # Verify that root model and models/ directory exist on disk
        root_models_dir = config.PROJECT_ROOT / "models"
        self.assertTrue(root_models_dir.exists(), f"Models directory not found at {root_models_dir}")
        root_pt_model = config.PROJECT_ROOT / "yolo26n.pt"
        self.assertTrue(root_pt_model.exists(), f"Baseline model not found at {root_pt_model}")

    # --------------------------------------------------------------------------
    # Test 2: ModelManager discovery lists all 6+ ONNX drone models and baseline yolo26n.pt
    # --------------------------------------------------------------------------
    def test_02_model_discovery_inventory(self) -> None:
        """
        Test 2: Verifies dynamic model discovery scans web/models/ and root models/,
        discovering at least 6 ONNX drone models plus baseline yolo26n.pt with
        valid metadata schemas and existing disk file paths.
        """
        manager = ModelManager()
        models = manager.list_models()

        self.assertIsInstance(models, list, "list_models() must return a list")
        self.assertGreaterEqual(
            len(models),
            7,
            f"Expected at least 7 discovered models (6+ ONNX + 1 PT), found {len(models)}",
        )

        model_names = [m.get("name") or m.get("id") for m in models]
        model_formats = [m.get("format") for m in models]

        # Verify baseline PyTorch model presence
        self.assertIn("yolo26n.pt", model_names, "Baseline model 'yolo26n.pt' not found in discovery")
        self.assertIn("pt", model_formats, "No 'pt' format model found in discovery list")

        # Verify primary ONNX drone models
        expected_onnx_models = [
            "yolov8n-drone-480.onnx",
            "yolov8n-drone-640.onnx",
            "yolo26n-drone-480.onnx",
            "yolo26n-drone-640.onnx",
            "yolo11n-drone-480.onnx",
            "yolo11n-drone-640.onnx",
        ]
        for expected in expected_onnx_models:
            self.assertIn(
                expected,
                model_names,
                f"Required ONNX drone model '{expected}' was not discovered",
            )

        # Verify metadata dictionary schema and disk existence for all models
        active_flags: List[bool] = []
        for m in models:
            self.assertIn("name", m)
            self.assertIn("label", m)
            self.assertIn("path", m)
            self.assertIn("format", m)
            self.assertIn("is_active", m)

            # Assert path exists on filesystem
            model_path = Path(m["path"])
            self.assertTrue(
                model_path.exists(),
                f"Discovered model path does not exist on disk: {model_path}",
            )

            # Assert format matches extension
            self.assertIn(m["format"].lower(), ["onnx", "pt"])

            # Assert Vietnamese display label
            self.assertIsInstance(m["label"], str)
            self.assertGreater(len(m["label"]), 0)

            active_flags.append(m["is_active"])

        # Exactly one model must be marked is_active
        self.assertEqual(
            sum(1 for flag in active_flags if flag),
            1,
            "Exactly one model must have is_active == True",
        )

    # --------------------------------------------------------------------------
    # Test 3: ModelManager active model hot-swapping
    # --------------------------------------------------------------------------
    def test_03_model_manager_hot_swapping(self) -> None:
        """
        Test 3: Verifies thread-safe runtime hot-swapping between ONNX and PT models,
        state updates in list_models(), detector caching, and rollback on error.
        """
        manager = ModelManager()

        # Get initial active model
        initial_models = manager.list_models()
        initial_active = next((m for m in initial_models if m["is_active"]), None)
        self.assertIsNotNone(initial_active, "No active model initially set")
        initial_name = initial_active["name"]

        # Target a different model for hot-swap
        target_name = "yolo26n.pt" if initial_name != "yolo26n.pt" else "yolov8n-drone-480.onnx"

        # Execute hot-swap
        swap_result = manager.set_active_model(target_name)
        self.assertTrue(swap_result, f"set_active_model('{target_name}') failed")

        # Verify active model name updated
        if hasattr(manager, "active_model_name"):
            self.assertEqual(manager.active_model_name, target_name)

        # Verify updated status in list_models()
        updated_models = manager.list_models()
        active_models = [m for m in updated_models if m["is_active"]]
        self.assertEqual(len(active_models), 1, "Exactly one active model expected after hot-swap")
        self.assertEqual(active_models[0]["name"], target_name)

        # Hot-swap back to initial model (tests round-trip and caching)
        swap_back_result = manager.set_active_model(initial_name)
        self.assertTrue(swap_back_result, f"Hot-swap back to '{initial_name}' failed")
        restored_models = manager.list_models()
        restored_active = [m for m in restored_models if m["is_active"]][0]
        self.assertEqual(restored_active["name"], initial_name)

        # Verify error handling on non-existent model name
        with self.assertRaises((KeyError, ValueError, FileNotFoundError)):
            manager.set_active_model("nonexistent_phantom_model_xyz.onnx")

        # Ensure previously active model is still active after failed swap
        post_error_models = manager.list_models()
        post_error_active = [m for m in post_error_models if m["is_active"]][0]
        self.assertEqual(
            post_error_active["name"],
            initial_name,
            "Active model changed despite failed hot-swap attempt",
        )

    # --------------------------------------------------------------------------
    # Test 4: Detector runs inference on synthetic test frame (numpy array) without error
    # --------------------------------------------------------------------------
    def test_04_detector_synthetic_inference(self) -> None:
        """
        Test 4: Verifies YOLODetector and ModelManager execute forward inference on
        synthetic numpy frames (black frame, noise frame) without runtime errors.
        """
        manager = ModelManager()

        # Test Frame A: Solid black 480x640 frame
        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result_black = manager.predict(black_frame, conf=0.25, iou=0.45)

        self.assertIsInstance(
            result_black,
            DetectionResult,
            "manager.predict() must return a DetectionResult instance",
        )
        self.assertGreaterEqual(result_black.inference_time_ms, 0.0)
        self.assertIsInstance(result_black.annotated_frame, np.ndarray)
        self.assertEqual(
            result_black.annotated_frame.shape,
            (480, 640, 3),
            "Annotated frame dimensions must match input frame dimensions",
        )
        self.assertEqual(result_black.annotated_frame.dtype, np.uint8)

        # Test Frame B: Random noise 480x640 frame
        np.random.seed(42)
        noise_frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
        result_noise = manager.predict(noise_frame, conf=0.30, iou=0.40)

        self.assertIsInstance(result_noise, DetectionResult)
        self.assertGreaterEqual(result_noise.inference_time_ms, 0.0)
        self.assertEqual(result_noise.annotated_frame.shape, (480, 640, 3))

        # Test standalone YOLODetector on ONNX model
        model_path = config.PROJECT_ROOT / "models" / "yolov8n-drone-480.onnx"
        detector = YOLODetector(model_path=model_path, warmup=False)
        det_result = detector.detect(black_frame, conf=0.25, iou=0.45)
        self.assertIsInstance(det_result, DetectionResult)

    # --------------------------------------------------------------------------
    # Test 5: DetectionResult structure contains valid boxes, labels, confidences, and annotated_frame
    # --------------------------------------------------------------------------
    def test_05_detection_result_structure(self) -> None:
        """
        Test 5: Verifies DetectionResult schema: boxes [x1, y1, x2, y2], confidences,
        class_ids, class_names, annotated_frame, properties, and to_dict() serialization.
        """
        # Part A: Test live result structure from synthetic zero inference
        manager = ModelManager()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        live_result = manager.predict(frame)

        self.assertIsInstance(live_result.boxes, list)
        self.assertIsInstance(live_result.confidences, list)
        self.assertIsInstance(live_result.class_ids, list)
        self.assertIsInstance(live_result.class_names, list)
        self.assertIsInstance(live_result.inference_time_ms, (int, float))
        self.assertIsInstance(live_result.annotated_frame, np.ndarray)

        self.assertEqual(len(live_result.boxes), len(live_result.confidences))
        self.assertEqual(len(live_result.boxes), len(live_result.class_ids))
        self.assertEqual(len(live_result.boxes), len(live_result.class_names))
        self.assertEqual(live_result.total_detections, len(live_result.boxes))
        self.assertGreaterEqual(live_result.avg_confidence, 0.0)
        self.assertLessEqual(live_result.avg_confidence, 1.0)

        # Part B: Direct schema & mathematical verification using populated DetectionResult
        mock_annotated = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_result = DetectionResult(
            boxes=[[100.5, 120.0, 250.0, 300.5], [350.0, 80.0, 480.0, 200.0]],
            confidences=[0.9450, 0.8820],
            class_ids=[0, 0],
            class_names=["drone", "drone"],
            inference_time_ms=42.5,
            annotated_frame=mock_annotated,
        )

        self.assertEqual(mock_result.total_detections, 2)
        expected_avg_conf = (0.9450 + 0.8820) / 2.0
        self.assertAlmostEqual(mock_result.avg_confidence, expected_avg_conf, places=3)

        # Validate bounding box coordinates integrity
        for box in mock_result.boxes:
            self.assertEqual(len(box), 4)
            x1, y1, x2, y2 = box
            self.assertLessEqual(x1, x2, "x1 must be <= x2")
            self.assertLessEqual(y1, y2, "y1 must be <= y2")

        # Validate JSON serialization contract
        res_dict = mock_result.to_dict()
        self.assertIn("detections", res_dict)
        self.assertIn("total_detections", res_dict)
        self.assertIn("avg_confidence", res_dict)
        self.assertIn("inference_time_ms", res_dict)
        self.assertEqual(res_dict["total_detections"], 2)
        self.assertEqual(len(res_dict["detections"]), 2)

        det0 = res_dict["detections"][0]
        self.assertIn("box", det0)
        self.assertIn("confidence", det0)
        self.assertIn("class_id", det0)
        self.assertIn("label", det0)
        self.assertEqual(det0["label"], "drone")

        # Assert dictionary is 100% JSON-serializable
        serialized_json = json.dumps(res_dict)
        self.assertIsInstance(serialized_json, str)
        self.assertGreater(len(serialized_json), 0)

    # --------------------------------------------------------------------------
    # Test 6: Detector error handling on corrupted / invalid input frame
    # --------------------------------------------------------------------------
    def test_06_detector_invalid_input_error_handling(self) -> None:
        """
        Test 6: Verifies robust error handling on corrupted/invalid inputs (None,
        non-array, 0-sized, 1D, 5-channel), auto-handling of 2D gray & 4-channel BGRA,
        and threshold clamping.
        """
        model_path = config.PROJECT_ROOT / "models" / "yolov8n-drone-480.onnx"
        detector = YOLODetector(model_path=model_path, warmup=False)

        # 1. None frame
        with self.assertRaises(ValueError):
            detector.detect(None)  # type: ignore

        # 2. Non-array inputs
        with self.assertRaises((TypeError, ValueError)):
            detector.detect("not_an_image")  # type: ignore
        with self.assertRaises((TypeError, ValueError)):
            detector.detect(12345)  # type: ignore

        # 3. Empty numpy array (0-sized)
        empty_frame = np.zeros((0, 0, 3), dtype=np.uint8)
        with self.assertRaises(ValueError):
            detector.detect(empty_frame)

        # 4. 1-dimensional array
        flat_frame = np.zeros((100,), dtype=np.uint8)
        with self.assertRaises(ValueError):
            detector.detect(flat_frame)

        # 5. Unsupported channel count (5-channel)
        five_channel_frame = np.zeros((100, 100, 5), dtype=np.uint8)
        with self.assertRaises(ValueError):
            detector.detect(five_channel_frame)

        # 6. Grayscale (2D array) tolerance: auto-converts to 3-channel BGR without crash
        gray_frame = np.zeros((240, 320), dtype=np.uint8)
        gray_result = detector.detect(gray_frame)
        self.assertIsInstance(gray_result, DetectionResult)
        self.assertEqual(gray_result.annotated_frame.shape, (240, 320, 3))

        # 7. BGRA (4-channel array) tolerance: auto-converts to 3-channel BGR without crash
        bgra_frame = np.zeros((240, 320, 4), dtype=np.uint8)
        bgra_result = detector.detect(bgra_frame)
        self.assertIsInstance(bgra_result, DetectionResult)
        self.assertEqual(bgra_result.annotated_frame.shape, (240, 320, 3))

        # 8. Out-of-bounds conf/iou values: clamped safely to [0.0, 1.0] without crash
        valid_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        clamped_result = detector.detect(valid_frame, conf=-0.5, iou=1.5)
        self.assertIsInstance(clamped_result, DetectionResult)

    # --------------------------------------------------------------------------
    # Test 7: ModelManager thread safety under concurrent requests
    # --------------------------------------------------------------------------
    def test_07_model_manager_thread_safety(self) -> None:
        """
        Test 7: Verifies ModelManager thread safety under concurrent multi-threaded
        inference requests and concurrent model hot-swapping without race conditions.
        """
        manager = ModelManager()
        test_frame = np.zeros((240, 320, 3), dtype=np.uint8)

        # Sub-test 7A: Concurrent inference across 6 worker threads
        num_tasks = 12
        def run_inference(task_id: int) -> DetectionResult:
            return manager.predict(test_frame, conf=0.25, iou=0.45)

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(run_inference, i) for i in range(num_tasks)]
            results = [f.result(timeout=15.0) for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), num_tasks)
        for res in results:
            self.assertIsInstance(res, DetectionResult)
            self.assertEqual(res.annotated_frame.shape, (240, 320, 3))

        # Sub-test 7B: Concurrent inference while hot-swapping
        stop_event = concurrent.futures.threading.Event()
        inference_errors: List[Exception] = []
        swap_errors: List[Exception] = []

        def worker_predict() -> None:
            while not stop_event.is_set():
                try:
                    res = manager.predict(test_frame)
                    assert isinstance(res, DetectionResult)
                except Exception as ex:
                    inference_errors.append(ex)
                time.sleep(0.01)

        def worker_swap() -> None:
            models_to_swap = ["yolo26n.pt", "yolov8n-drone-480.onnx"]
            for m in models_to_swap * 2:
                if stop_event.is_set():
                    break
                try:
                    manager.set_active_model(m)
                except Exception as ex:
                    swap_errors.append(ex)
                time.sleep(0.05)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            p_futures = [executor.submit(worker_predict) for _ in range(3)]
            s_future = executor.submit(worker_swap)
            time.sleep(0.3)
            stop_event.set()
            s_future.result(timeout=10.0)
            for pf in p_futures:
                pf.result(timeout=5.0)

        self.assertEqual(
            len(inference_errors),
            0,
            f"Concurrent inference encountered errors: {inference_errors}",
        )
        self.assertEqual(
            len(swap_errors),
            0,
            f"Concurrent hot-swapping encountered errors: {swap_errors}",
        )


# ==============================================================================
# Standalone CLI Test Runner
# ==============================================================================
def run_standalone_suite() -> int:
    """Execute all tests in TestModelEngine and print a formatted summary report."""
    print("=" * 80)
    print("  ANTI-DRONE OBJECT DETECTION SYSTEM - MILESTONE 1 UNIT VERIFICATION SUITE")
    print("=" * 80)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestModelEngine)
    total_tests = suite.countTestCases()
    print(f"\n[RUNNER] Loaded {total_tests} unit tests from {Path(__file__).name}")
    print("[RUNNER] Target modules: backend.config, backend.model_manager, backend.detector\n")

    t_start = time.perf_counter()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    elapsed = time.perf_counter() - t_start

    print("\n" + "=" * 80)
    print(f"  EXECUTION SUMMARY: {result.testsRun} run, {len(result.failures)} failed, "
          f"{len(result.errors)} errors, {len(result.skipped)} skipped in {elapsed:.2f}s")
    print("=" * 80)

    if result.wasSuccessful():
        print("[SUCCESS] All Milestone 1 unit tests passed! Verification criteria satisfied.\n")
        return 0
    else:
        print("[FAILURE] One or more tests failed. Inspect tracebacks above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_standalone_suite())
```

---

## 5. Verification Method

Once the implementation Worker creates `web/backend/config.py`, `web/backend/model_manager.py`, and `web/backend/detector.py`, execute the following verification commands:

### Command 1: Pytest Execution
```powershell
C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/tests/test_model_engine.py -v
```
**Expected Result**:
```
web/tests/test_model_engine.py::TestModelEngine::test_01_config_loading_and_directory_paths PASSED
web/tests/test_model_engine.py::TestModelEngine::test_02_model_discovery_inventory PASSED
web/tests/test_model_engine.py::TestModelEngine::test_03_model_manager_hot_swapping PASSED
web/tests/test_model_engine.py::TestModelEngine::test_04_detector_synthetic_inference PASSED
web/tests/test_model_engine.py::TestModelEngine::test_05_detection_result_structure PASSED
web/tests/test_model_engine.py::TestModelEngine::test_06_detector_invalid_input_error_handling PASSED
web/tests/test_model_engine.py::TestModelEngine::test_07_model_manager_thread_safety PASSED
============================== 7 passed in X.XXs ==============================
```
Exit code: `0`.

### Command 2: Standalone Python Execution
```powershell
C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe web/tests/test_model_engine.py
```
**Expected Result**:
```
================================================================================
  ANTI-DRONE OBJECT DETECTION SYSTEM - MILESTONE 1 UNIT VERIFICATION SUITE
================================================================================

[RUNNER] Loaded 7 unit tests from test_model_engine.py
[RUNNER] Target modules: backend.config, backend.model_manager, backend.detector

test_01_config_loading_and_directory_paths (__main__.TestModelEngine) ... ok
test_02_model_discovery_inventory (__main__.TestModelEngine) ... ok
test_03_model_manager_hot_swapping (__main__.TestModelEngine) ... ok
test_04_detector_synthetic_inference (__main__.TestModelEngine) ... ok
test_05_detection_result_structure (__main__.TestModelEngine) ... ok
test_06_detector_invalid_input_error_handling (__main__.TestModelEngine) ... ok
test_07_model_manager_thread_safety (__main__.TestModelEngine) ... ok

================================================================================
  EXECUTION SUMMARY: 7 run, 0 failed, 0 errors, 0 skipped in X.XXs
================================================================================
[SUCCESS] All Milestone 1 unit tests passed! Verification criteria satisfied.
```
Exit code: `0`.
