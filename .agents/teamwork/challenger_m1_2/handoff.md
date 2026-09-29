# Milestone 1 Empirical Boundary & Numerical Challenge Handoff Report

**Author**: `challenger_m1_2` (Empirical Boundary & Numerical Challenger)  
**Working Directory**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\.agents\teamwork\challenger_m1_2\`  
**Target Milestone**: Milestone 1 (Backend Model Engine & Dynamic Discovery)  
**Parent Agent**: `orchestrator_1` (`595c75fc-66e7-4215-9d43-217f246c6ae5`)  
**Timestamp**: 2026-09-28T06:58:00Z  
**Explicit Verdict**: **REJECT**

---

## 1. Observation

Adversarial stress script executed at `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\.agents\teamwork\challenger_m1_2\test_boundary_stress.py` targeting `web/backend/detector.py`:

### Observation 1.1: Robust Behaviors (Passed)
- Extreme resolutions (1x1, 1080p, 1000x10, 10x1000) and non-contiguous numpy slices (`arr[::2, ::2, :]`) execute cleanly without errors.
- Boundary conf/iou values (`conf=-0.5, 1.5`, `iou=-0.1, 2.0`) are clamped to `[0.0, 1.0]` at lines 192-193.
- `None`, empty array `(0, 0, 3)`, 1D array `(100,)`, and 4D tensor `(1, 480, 640, 3)` raise informative `ValueError` / `TypeError` at lines 172-190.

### Observation 1.2: Failure Mode A — NaN Array Not Rejected & Dtype Invariance Broken
When testing NaN input:
```python
nan_arr = np.full((100, 100, 3), np.nan, dtype=np.float32)
res = detector.detect(nan_arr)
```
- Line 172-190 in `detector.py` lacks NaN check (`np.isnan(frame).any()`).
- No `ValueError` or `TypeError` is raised.
- `res.annotated_frame.dtype` returns `float32` (instead of `uint8`) and retains NaNs (`np.isnan(res.annotated_frame).any() == True`), violating the visualization uint8 contract.

### Observation 1.3: Failure Mode B — Non-uint8 Frame Crashes OpenCV hal::resize
When testing non-uint8 numeric inputs:
```python
int32_arr = np.zeros((100, 100, 3), dtype=np.int32)
detector.detect(int32_arr)
```
Unhandled C++ exception raised inside Ultralytics preprocessing:
```
cv2.error: OpenCV(5.0.0) D:\a\opencv-python\opencv-python\opencv\modules\imgproc\src\resize.cpp:4095: error: (-215:Assertion failed) func != 0 in function 'cv::hal::resize'
```

---

## 2. Logic Chain

1. **Mandate Requirement 3**: Demands: *"Invalid inputs: empty array, None, 1D array, 4D tensor, NaN-filled array. Assert informative ValueError/TypeError without unhandled crash."*
   - As shown in Observation 1.2, passing `nan_arr` silently succeeds without raising `ValueError` or `TypeError`.
   - As shown in Observation 1.3, passing non-uint8 arrays triggers an unhandled OpenCV C++ assertion failure instead of an informative Python exception.

2. **Mandate Requirement 4**: Demands: *"Visualization verification: ensure annotated_frame has identical shape and uint8 dtype across all tests."*
   - As shown in Observation 1.2, `annotated_frame` inherits `float32` from floating input arrays rather than guaranteeing `np.uint8`. This breaks downstream MJPEG encoding (`cv2.imencode`).

3. **Conclusion Derivation**: Because two explicit boundary requirements failed verification, Milestone 1 must be marked **REJECT** pending a brief input validation patch.

---

## 3. Caveats

- In normal operational pipelines, OpenCV VideoCapture and JPEG decoders (`cv2.imdecode`) produce `uint8` BGR buffers, so these edge cases will not trigger during standard happy-path camera/file streams.
- CPU inference performance across all valid inputs exceeded targets (>20 FPS).

---

## 4. Conclusion

**Verdict: REJECT**

Recommended resolution for `worker_m1_1`:
In `web/backend/detector.py` under `YOLODetector.detect()`, add dtype and NaN validation:
```python
if frame.dtype != np.uint8:
    if np.issubdtype(frame.dtype, np.floating) and np.isnan(frame).any():
        raise ValueError("Input frame contains NaN values")
    if frame.dtype != np.uint8:
        raise TypeError(f"Expected frame dtype uint8, got {frame.dtype}")
```

---

## 5. Verification Method

Run the adversarial stress script:
```powershell
C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe .agents\teamwork\challenger_m1_2\test_boundary_stress.py
```
Direct reproduction of failures:
```powershell
C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe -c "import sys, numpy as np; sys.path.insert(0, 'web'); from backend.detector import YOLODetector; d = YOLODetector('models/yolov8n-drone-480.onnx', warmup=False); d.detect(np.zeros((100, 100, 3), dtype=np.int32))"
```
**Invalidation Condition**: Both commands raise clean `ValueError` or `TypeError`, and `res.annotated_frame.dtype == np.uint8`.
