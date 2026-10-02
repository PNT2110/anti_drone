# Scope 21 — Pi runtime parity

Status: **PASS** for all 10 eligible candidates.

The fixed Scope 20 gate was retained: confidence absolute difference `<= 0.05`, bbox IoU `>= 0.95`, exact class, and exact detection count. The Pi runner used exactly one external NMS for `[1,5,N]` YOLOv8/YOLOv11 outputs and no extra NMS for `[1,300,6]` YOLO26 outputs.

| Run | Backend | Images passing | Max confidence diff | Min bbox IoU | Result |
|---|---:|---:|---:|---:|---|
| `scope18-yolo26n-480` | onnx | 8/8 | 0.000591 | 0.995223 | `PI_BENCHMARK_PASS` |
| `scope18-yolo26n-640` | onnx | 8/8 | 0.000001 | 0.999998 | `PI_BENCHMARK_PASS` |
| `scope18-yolov11n-480` | ncnn | 8/8 | 0.001989 | 0.981266 | `PI_BENCHMARK_PASS` |
| `scope18-yolov11n-480` | onnx | 8/8 | 0.000276 | 0.995603 | `PI_BENCHMARK_PASS` |
| `scope18-yolov11n-640` | ncnn | 8/8 | 0.002133 | 0.970178 | `PI_BENCHMARK_PASS` |
| `scope18-yolov11n-640` | onnx | 8/8 | 0.000000 | 0.999996 | `PI_BENCHMARK_PASS` |
| `scope18-yolov8n-480` | ncnn | 8/8 | 0.001234 | 0.971743 | `PI_BENCHMARK_PASS` |
| `scope18-yolov8n-480` | onnx | 8/8 | 0.000609 | 0.993758 | `PI_BENCHMARK_PASS` |
| `scope18-yolov8n-640` | ncnn | 8/8 | 0.002689 | 0.977867 | `PI_BENCHMARK_PASS` |
| `scope18-yolov8n-640` | onnx | 8/8 | 0.000000 | 0.999998 | `PI_BENCHMARK_PASS` |
