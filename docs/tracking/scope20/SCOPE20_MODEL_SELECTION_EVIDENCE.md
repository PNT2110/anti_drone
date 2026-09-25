# Scope 20 — Model-selection evidence

Selection uses frozen Scope 18 VAL metrics only; no test metric was opened. Host FPS is copied from Scope 19 as diagnostic reference only, not Pi evidence:

| Run | Backend | Frozen mAP50-95 | Frozen recall | Parameters | Scope 19 host FPS (diagnostic) | Parity | INT8 status | Pi status | Scope 20 role |
|---|---|---:|---:|---:|---:|---|---|---|---|
| `scope18-yolov8n-640` | `onnx` | 0.63360 | 0.98665 | 3,011,043 | 17.27 | `PARITY_PASS` | `BLOCKED` | `PENDING_PI5` | CANDIDATE |
| `scope18-yolov8n-640` | `ncnn` | 0.63360 | 0.98665 | 3,011,043 | 27.01 | `PARITY_PASS` | `BLOCKED` | `PENDING_PI5` | CANDIDATE |
| `scope18-yolov8n-480` | `onnx` | 0.62836 | 0.98689 | 3,011,043 | 31.14 | `PARITY_PASS` | `BLOCKED` | `PENDING_PI5` | CANDIDATE |
| `scope18-yolov8n-480` | `ncnn` | 0.62836 | 0.98689 | 3,011,043 | 45.08 | `PARITY_PASS` | `BLOCKED` | `PENDING_PI5` | CANDIDATE |
| `scope18-yolov11n-640` | `onnx` | 0.62983 | 0.98725 | 2,590,035 | 19.38 | `PARITY_PASS` | `BLOCKED` | `PENDING_PI5` | CANDIDATE |
| `scope18-yolov11n-640` | `ncnn` | 0.62983 | 0.98725 | 2,590,035 | 25.28 | `PARITY_PASS` | `BLOCKED` | `PENDING_PI5` | CANDIDATE |
| `scope18-yolov11n-480` | `onnx` | 0.62466 | 0.98583 | 2,590,035 | 32.34 | `PARITY_PASS` | `BLOCKED` | `PENDING_PI5` | CANDIDATE |
| `scope18-yolov11n-480` | `ncnn` | 0.62466 | 0.98583 | 2,590,035 | 42.64 | `PARITY_PASS` | `BLOCKED` | `PENDING_PI5` | CANDIDATE |
| `scope18-yolo26n-640` | `onnx` | 0.63170 | 0.98543 | 2,504,190 | 27.26 | `PARITY_PASS` | `BLOCKED` | `PENDING_PI5` | CANDIDATE |
| `scope18-yolo26n-640` | `ncnn` | 0.63170 | 0.98543 | 2,504,190 | 25.52 | `PARITY_FAIL` | `BLOCKED` | `PENDING_PI5` | DIAGNOSTIC_ONLY |
| `scope18-yolo26n-480` | `onnx` | 0.62691 | 0.98264 | 2,504,190 | 41.17 | `PARITY_PASS` | `BLOCKED` | `PENDING_PI5` | CANDIDATE |
| `scope18-yolo26n-480` | `ncnn` | 0.62691 | 0.98264 | 2,504,190 | 43.67 | `PARITY_FAIL` | `BLOCKED` | `PENDING_PI5` | DIAGNOSTIC_ONLY |

The 10 passing backend pairs are deployment candidates pending real Pi 5 evidence and intended quantization decision. The 2 YOLO26-NCNN pairs are dominated on compatibility by their output-contract mismatch and remain diagnostic-only; artifacts are retained. No hidden weighted score and no production model freeze is created.
