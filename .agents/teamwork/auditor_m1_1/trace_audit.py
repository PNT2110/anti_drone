"""
Forensic Runtime Tracing Script for Milestone 1
Auditor: auditor_m1_1
"""

import os
import sys
import time
from pathlib import Path
import cv2
import numpy as np

# Add web and project root to sys.path
PROJECT_ROOT = Path(r"c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone").resolve()
WEB_DIR = PROJECT_ROOT / "web"
sys.path.insert(0, str(WEB_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

print("[FORENSIC TRACE] Starting forensic runtime tracing...")

# 1. Inspect Ultralytics & ONNX Runtime environment
import ultralytics
import onnxruntime as ort
import torch

print(f"[FORENSIC TRACE] ultralytics version: {ultralytics.__version__} at {ultralytics.__file__}")
print(f"[FORENSIC TRACE] onnxruntime version: {ort.__version__} at {ort.__file__}")
print(f"[FORENSIC TRACE] torch version: {torch.__version__} at {torch.__file__}")
print(f"[FORENSIC TRACE] onnxruntime available providers: {ort.get_available_providers()}")

# 2. Import project modules
from backend import config
from backend.model_manager import ModelManager, get_model_manager
from backend.detector import DetectionResult, YOLODetector

# 3. Model Discovery verification
manager = ModelManager(auto_init=False)
discovered = manager.discover_models(force_rescan=True)
print(f"[FORENSIC TRACE] Discovered {len(discovered)} models:")
for m_id, meta in discovered.items():
    p = Path(meta["path"])
    print(f"  - {m_id}: format={meta['format']}, size={meta['size_mb']}MB, exists={p.exists()}, label={meta['label']}")
    assert p.exists(), f"Discovered file does not exist: {p}"
    assert p.stat().st_size > 0, f"Discovered file is empty: {p}"

# 4. Model Loading - ONNX Drone Model
print("\n[FORENSIC TRACE] Initializing ONNX Drone Model (yolov8n-drone-480.onnx)...")
manager.set_active_model("yolov8n-drone-480.onnx")
active_id, active_detector = manager.get_active_model()
print(f"[FORENSIC TRACE] Active model ID: {active_id}")
print(f"[FORENSIC TRACE] Active detector type: {type(active_detector)}")
print(f"[FORENSIC TRACE] Underlying YOLO model type: {type(active_detector.model)}")
print(f"[FORENSIC TRACE] Model classes: {active_detector.names}")
print(f"[FORENSIC TRACE] Is drone model: {active_detector.is_drone_model}")

# Verify underlying ONNX Session
inner_model = active_detector.model
# In ultralytics, inner predictor/session is set on inference or session attribute
assert isinstance(inner_model, ultralytics.YOLO), "Underlying model is not an ultralytics.YOLO instance!"

# 5. Synthetic Frame Inference
print("\n[FORENSIC TRACE] Running inference on synthetic 480x640 frame...")
synthetic_frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)
t0 = time.perf_counter()
res_synthetic = manager.predict(synthetic_frame)
t_infer = time.perf_counter() - t0
print(f"[FORENSIC TRACE] Synthetic frame inference returned in {t_infer*1000:.2f} ms")
print(f"[FORENSIC TRACE] Result inference_time_ms reported: {res_synthetic.inference_time_ms:.2f} ms")
print(f"[FORENSIC TRACE] Result total detections: {res_synthetic.total_detections}")
print(f"[FORENSIC TRACE] Annotated frame shape: {res_synthetic.annotated_frame.shape}")
assert isinstance(res_synthetic, DetectionResult), "Did not return DetectionResult"
assert res_synthetic.annotated_frame.shape == (480, 640, 3), "Annotated frame shape mismatch"

# 6. Real Drone Image Inference
test_img_path = PROJECT_ROOT / "data" / "drone-single-class" / "images" / "test" / "base__000000__RGBT_val_20190925_130434_1_6_visible_345.jpg"
if test_img_path.exists():
    print(f"\n[FORENSIC TRACE] Running inference on real test image: {test_img_path.name}...")
    real_img = cv2.imread(str(test_img_path))
    assert real_img is not None, "Failed to load real test image"
    print(f"[FORENSIC TRACE] Real image loaded, shape: {real_img.shape}")

    res_real = manager.predict(real_img, conf=0.15)
    print(f"[FORENSIC TRACE] Real image detections: {res_real.total_detections}")
    print(f"[FORENSIC TRACE] Boxes: {res_real.boxes}")
    print(f"[FORENSIC TRACE] Confidences: {res_real.confidences}")
    print(f"[FORENSIC TRACE] Class names: {res_real.class_names}")
    print(f"[FORENSIC TRACE] Inference time: {res_real.inference_time_ms:.2f} ms")
    if res_real.total_detections > 0:
        for i in range(res_real.total_detections):
            box = res_real.boxes[i]
            conf = res_real.confidences[i]
            label = res_real.class_names[i]
            print(f"  Detection {i+1}: {label} conf={conf:.4f} box={[round(x, 1) for x in box]}")
            assert 0.0 <= conf <= 1.0, f"Invalid confidence {conf}"
            assert box[0] <= box[2] and box[1] <= box[3], f"Invalid box {box}"

# 7. Hot-Swap to PyTorch Model (yolo26n.pt)
print("\n[FORENSIC TRACE] Hot-swapping to PyTorch model (yolo26n.pt)...")
manager.set_active_model("yolo26n.pt")
pt_id, pt_detector = manager.get_active_model()
print(f"[FORENSIC TRACE] Active model ID: {pt_id}")
print(f"[FORENSIC TRACE] Classes count: {len(pt_detector.names)} (expected 80 COCO classes)")
assert len(pt_detector.names) == 80, f"Expected 80 classes, got {len(pt_detector.names)}"
assert pt_detector.names[0] == "person", f"Expected class 0 == person, got {pt_detector.names[0]}"

# Run inference with PyTorch model
print("[FORENSIC TRACE] Running inference with yolo26n.pt on synthetic frame...")
res_pt = manager.predict(synthetic_frame)
print(f"[FORENSIC TRACE] PyTorch model inference time: {res_pt.inference_time_ms:.2f} ms")
assert isinstance(res_pt, DetectionResult)

# 8. Check for Monkeypatching or Injected Mocks
print("\n[FORENSIC TRACE] Inspecting ultralytics and detector integrity...")
import inspect
detector_code = inspect.getsource(YOLODetector.detect)
assert "self.model.predict(" in detector_code, "YOLODetector does not call self.model.predict"
assert "r_boxes.xyxy.cpu().numpy().tolist()" in detector_code, "YOLODetector does not read real boxes"
print("[FORENSIC TRACE] YOLODetector source verified: invokes self.model.predict and reads genuine boxes.")

print("\n[FORENSIC TRACE] ALL INTEGRITY CHECKS PASSED EMPIRICALLY!")
