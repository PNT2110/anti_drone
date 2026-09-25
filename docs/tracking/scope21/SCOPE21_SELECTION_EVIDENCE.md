# Scope 21 — Selection evidence

Status: **EVIDENCE COMPLETE; PRODUCTION FREEZE NOT AUTHORIZED**.

The table combines frozen Scope 18 VAL metrics with real Pi 5 FP32 measurements. Scope 20 INT8 remains `BLOCKED`; it was not changed and was not used to silently eliminate any candidate. No hidden weighted score or single production winner is declared.

| Run | Backend | Size | VAL mAP50-95 | VAL recall | Pi FPS | Model MiB | Pi result | INT8 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `scope18-yolo26n-480` | onnx | 480 | 0.62691 | 0.98264 | 14.360 | 9.280 | `PI_BENCHMARK_PASS` | SCOPE20 BLOCKED |
| `scope18-yolo26n-640` | onnx | 640 | 0.63170 | 0.98543 | 7.979 | 9.350 | `PI_BENCHMARK_PASS` | SCOPE20 BLOCKED |
| `scope18-yolov11n-480` | ncnn | 480 | 0.62466 | 0.98583 | 22.055 | 9.992 | `PI_BENCHMARK_PASS` | SCOPE20 BLOCKED |
| `scope18-yolov11n-480` | onnx | 480 | 0.62466 | 0.98583 | 12.371 | 10.043 | `PI_BENCHMARK_PASS` | SCOPE20 BLOCKED |
| `scope18-yolov11n-640` | ncnn | 640 | 0.62983 | 0.98725 | 11.754 | 10.034 | `PI_BENCHMARK_PASS` | SCOPE20 BLOCKED |
| `scope18-yolov11n-640` | onnx | 640 | 0.62983 | 0.98725 | 6.787 | 10.113 | `PI_BENCHMARK_PASS` | SCOPE20 BLOCKED |
| `scope18-yolov8n-480` | ncnn | 480 | 0.62836 | 0.98689 | 22.493 | 11.585 | `PI_BENCHMARK_PASS` | SCOPE20 BLOCKED |
| `scope18-yolov8n-480` | onnx | 480 | 0.62836 | 0.98689 | 11.747 | 11.627 | `PI_BENCHMARK_PASS` | SCOPE20 BLOCKED |
| `scope18-yolov8n-640` | ncnn | 640 | 0.63360 | 0.98665 | 11.726 | 11.627 | `PI_BENCHMARK_PASS` | SCOPE20 BLOCKED |
| `scope18-yolov8n-640` | onnx | 640 | 0.63360 | 0.98665 | 6.547 | 11.697 | `PI_BENCHMARK_PASS` | SCOPE20 BLOCKED |

All 10 eligible candidates are factual Pareto evidence for Research & Design review. The V3 TEST split remains locked and no production model was frozen.
