# Scope 20 — Backend contract

Preprocess contract: OpenCV BGR input → Ultralytics BGR-to-RGB → uint8 to float32 → divide by 255 → `LetterBox(auto=False, padding=114)` → NCHW → batch 1. Image size is the trained size, 480 or 640; no 320 path is used.

| Backend family | Raw shape | Decode | NMS |
|---|---|---|---|
| YOLOv8n / YOLOv11n PT, ONNX, NCNN | `[1,5,N]` | `xywh + class score` | external single-class NMS |
| YOLO26n PT, ONNX | `[1,300,6]` | `xyxy + confidence + class` | embedded end-to-end top-k/NMS |
| YOLO26n NCNN | `[1,5,N]` | raw standard detect contract | external NMS required; not parity-equivalent |

The harness applies NMS exactly once: standard `[1,5,N]` outputs use external NMS at confidence `0.25` and IoU `0.70`; `[1,300,6]` end-to-end outputs are thresholded without a second NMS. Coordinate restoration uses the same letterbox shape and original image shape.

ONNX graph contracts and NCNN native names remain recorded in `/run/media/pnt/APP/anti_drone/.runtime/scope19/backend_contracts.json`; Scope 20 raw-stage evidence is `/run/media/pnt/APP/anti_drone/.runtime/scope20/parity_trace.json`.
