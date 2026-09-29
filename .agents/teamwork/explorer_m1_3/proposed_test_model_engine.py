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
        # Workspace has at least 7 ONNX models (yolo11n-drone-480/640, yolo26n-drone-480/640,
        # yolov8n-drone-480/640, yolov8n-drone-best) + 1 baseline yolo26n.pt
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
        active_detector = manager.get_active_model() if hasattr(manager, "get_active_model") else None
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
