# Scope 20 — Corrected parity results

Acceptance gate unchanged from Scope 19: confidence absolute difference `<=0.05`, bbox IoU `>=0.95`, exact class, exact detection count. Diagnostic raw tolerance is only `atol=1e-4, rtol=1e-4`; it is not the acceptance gate.

| Run | Backend | Result | First-divergence summary |
|---|---|---|---|
| `scope18-yolov8n-640` | `onnx` | `PARITY_PASS` | none:8 |
| `scope18-yolov8n-640` | `ncnn` | `PARITY_PASS` | none:8 |
| `scope18-yolov8n-480` | `onnx` | `PARITY_PASS` | none:8 |
| `scope18-yolov8n-480` | `ncnn` | `PARITY_PASS` | none:8 |
| `scope18-yolov11n-640` | `onnx` | `PARITY_PASS` | none:8 |
| `scope18-yolov11n-640` | `ncnn` | `PARITY_PASS` | none:8 |
| `scope18-yolov11n-480` | `onnx` | `PARITY_PASS` | none:8 |
| `scope18-yolov11n-480` | `ncnn` | `PARITY_PASS` | none:8 |
| `scope18-yolo26n-640` | `onnx` | `PARITY_PASS` | none:8 |
| `scope18-yolo26n-640` | `ncnn` | `PARITY_FAIL` | output_contract:8 |
| `scope18-yolo26n-480` | `onnx` | `PARITY_PASS` | none:8 |
| `scope18-yolo26n-480` | `ncnn` | `PARITY_FAIL` | output_contract:8 |

Aggregate: **10 PARITY_PASS**, **2 PARITY_FAIL** across 12 corrected backend pairs. All 8 ONNX pairs and all 4 YOLOv8/YOLOv11 NCNN pairs pass. The two YOLO26 NCNN failures are output-contract failures on all 8 locked images. No test image was accessed.
