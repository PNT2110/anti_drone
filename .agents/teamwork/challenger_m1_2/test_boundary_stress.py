"""
Empirical Boundary & Numerical Stress Test Suite for Milestone 1.
Challenger: challenger_m1_2
Target: web/backend/detector.py and DetectionResult
"""

import sys
import traceback
from pathlib import Path
import numpy as np

# Add project root and web dir to sys.path
PROJECT_ROOT = Path(r"c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone")
WEB_DIR = PROJECT_ROOT / "web"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(WEB_DIR))

from backend.detector import YOLODetector, DetectionResult
from backend.model_manager import get_model_manager

print(f"[INIT] Python executable: {sys.executable}")
print(f"[INIT] Project root: {PROJECT_ROOT}")

# Discover models
model_path = PROJECT_ROOT / "models" / "yolov8n-drone-480.onnx"
if not model_path.exists():
    model_path = PROJECT_ROOT / "yolo26n.pt"

print(f"[INIT] Using model: {model_path}")
detector = YOLODetector(model_path=model_path, warmup=True)
print(f"[INIT] Detector initialized successfully. Model: {detector.model_path.name}")

results_summary = []

def run_test(name, test_func):
    print(f"\n--- RUNNING TEST: {name} ---")
    try:
        test_func()
        print(f"[PASS] {name}")
        results_summary.append((name, "PASS", "OK"))
    except AssertionError as ae:
        print(f"[FAIL] {name}: Assertion failed: {ae}")
        results_summary.append((name, "FAIL", str(ae)))
    except Exception as e:
        print(f"[ERROR] {name}: Unhandled exception: {type(e).__name__}: {e}")
        traceback.print_exc()
        results_summary.append((name, "ERROR", f"{type(e).__name__}: {e}"))

# ==============================================================================
# 1. Extreme Resolutions & Memory Layout
# ==============================================================================
def test_1x1_resolution():
    frame = np.zeros((1, 1, 3), dtype=np.uint8)
    res = detector.detect(frame, draw=True)
    assert isinstance(res, DetectionResult)
    assert res.annotated_frame.shape == (1, 1, 3), f"Expected (1, 1, 3), got {res.annotated_frame.shape}"
    assert res.annotated_frame.dtype == np.uint8, f"Expected uint8, got {res.annotated_frame.dtype}"

def test_1920x1080_resolution():
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    # Add a synthetic rectangle or drone-like patch
    frame[500:550, 900:960] = 200
    res = detector.detect(frame, draw=True)
    assert isinstance(res, DetectionResult)
    assert res.annotated_frame.shape == (1080, 1920, 3), f"Expected (1080, 1920, 3), got {res.annotated_frame.shape}"
    assert res.annotated_frame.dtype == np.uint8, f"Expected uint8, got {res.annotated_frame.dtype}"

def test_extreme_aspect_ratios():
    # Tall skinny
    frame_tall = np.zeros((1000, 10, 3), dtype=np.uint8)
    res_tall = detector.detect(frame_tall, draw=True)
    assert res_tall.annotated_frame.shape == (1000, 10, 3)
    assert res_tall.annotated_frame.dtype == np.uint8

    # Short wide
    frame_wide = np.zeros((10, 1000, 3), dtype=np.uint8)
    res_wide = detector.detect(frame_wide, draw=True)
    assert res_wide.annotated_frame.shape == (10, 1000, 3)
    assert res_wide.annotated_frame.dtype == np.uint8

def test_non_contiguous_array():
    base = np.zeros((200, 200, 3), dtype=np.uint8)
    # Slice with step > 1 creates non-contiguous array
    non_contig = base[::2, ::2, :]
    assert not non_contig.flags.c_contiguous, "Array should be non-contiguous"
    res = detector.detect(non_contig, draw=True)
    assert res.annotated_frame.shape == non_contig.shape
    assert res.annotated_frame.dtype == np.uint8

# ==============================================================================
# 2. Boundary Confidence & IoU Thresholds
# ==============================================================================
def test_boundary_conf_iou():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    threshold_pairs = [
        ("conf=0.0, iou=0.0", 0.0, 0.0),
        ("conf=1.0, iou=1.0", 1.0, 1.0),
        ("conf=-0.5, iou=-0.1 (underflow)", -0.5, -0.1),
        ("conf=1.5, iou=2.0 (overflow)", 1.5, 2.0),
        ("conf=0.5, iou=0.5 (standard)", 0.5, 0.5),
    ]
    for desc, conf, iou in threshold_pairs:
        res = detector.detect(frame, conf=conf, iou=iou, draw=True)
        assert isinstance(res, DetectionResult), f"Failed for {desc}"
        assert res.annotated_frame.shape == (480, 640, 3)
        assert res.annotated_frame.dtype == np.uint8

# ==============================================================================
# 3. Invalid Inputs Error Handling
# ==============================================================================
def test_invalid_none_input():
    try:
        detector.detect(None)
        assert False, "Expected ValueError/TypeError for None"
    except (ValueError, TypeError) as e:
        print(f"  Gracefully caught None: {type(e).__name__}: {e}")

def test_invalid_empty_array():
    try:
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        detector.detect(empty)
        assert False, "Expected ValueError for empty array"
    except ValueError as e:
        print(f"  Gracefully caught empty array: {type(e).__name__}: {e}")

def test_invalid_1d_array():
    try:
        arr1d = np.zeros((100,), dtype=np.uint8)
        detector.detect(arr1d)
        assert False, "Expected ValueError for 1D array"
    except ValueError as e:
        print(f"  Gracefully caught 1D array: {type(e).__name__}: {e}")

def test_invalid_4d_tensor():
    try:
        arr4d = np.zeros((1, 480, 640, 3), dtype=np.uint8)
        detector.detect(arr4d)
        assert False, "Expected ValueError for 4D array"
    except ValueError as e:
        print(f"  Gracefully caught 4D tensor: {type(e).__name__}: {e}")

def test_invalid_nan_array():
    try:
        nan_arr = np.full((100, 100, 3), np.nan, dtype=np.float32)
        detector.detect(nan_arr)
        # If it doesn't raise ValueError, did it succeed or fail silently?
        print("  Warning: nan_arr did not raise exception immediately")
    except (ValueError, TypeError) as e:
        print(f"  Gracefully caught NaN array: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"  Unhandled exception for NaN array: {type(e).__name__}: {e}")
        raise

# ==============================================================================
# 4. Visualization & Result Structure Verification
# ==============================================================================
def test_visualization_stability():
    shapes = [(1, 1, 3), (240, 320, 3), (720, 1280, 3), (100, 200)]
    for shape in shapes:
        frame = np.zeros(shape, dtype=np.uint8)
        res = detector.detect(frame, draw=True, draw_fps=True)
        expected_shape = shape if len(shape) == 3 else (*shape, 3)
        assert res.annotated_frame.shape == expected_shape, f"Mismatch: {res.annotated_frame.shape} vs {expected_shape}"
        assert res.annotated_frame.dtype == np.uint8, f"Mismatch dtype: {res.annotated_frame.dtype}"
        d = res.to_dict()
        assert "detections" in d
        assert "total_detections" in d
        assert "avg_confidence" in d
        assert "inference_time_ms" in d

# Run all tests
run_test("1x1 Resolution", test_1x1_resolution)
run_test("1920x1080 Resolution", test_1920x1080_resolution)
run_test("Extreme Aspect Ratios", test_extreme_aspect_ratios)
run_test("Non-Contiguous Array", test_non_contiguous_array)
run_test("Boundary Conf & IoU Thresholds", test_boundary_conf_iou)
run_test("Invalid Input: None", test_invalid_none_input)
run_test("Invalid Input: Empty Array", test_invalid_empty_array)
run_test("Invalid Input: 1D Array", test_invalid_1d_array)
run_test("Invalid Input: 4D Tensor", test_invalid_4d_tensor)
run_test("Invalid Input: NaN Array", test_invalid_nan_array)
run_test("Visualization Stability Across Shapes", test_visualization_stability)

print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)
for name, status, msg in results_summary:
    print(f"[{status}] {name}: {msg}")
