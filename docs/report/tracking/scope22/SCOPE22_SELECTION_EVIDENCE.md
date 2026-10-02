# Scope 22 — Selection evidence

Status: **INT8_PATH_BLOCKED; NO FREEZE-REVIEW CANDIDATE**.

| Candidate | Frozen VAL mAP50-95 | Frozen VAL recall | Scope 21 FP32 Pi FPS | Scope 22 INT8 Pi FPS | INT8 status | Decision |
|---|---:|---:|---:|---:|---|---|
| `scope18-yolov8n-480` | 0.62836 | 0.98689 | 22.493 | N/A | INT8_PATH_BLOCKED | FP32 baseline retained |
| `scope18-yolov8n-640` | 0.63360 | 0.98665 | 11.726 | N/A | INT8_PATH_BLOCKED | FP32 baseline retained |
| `scope18-yolov11n-480` | 0.62466 | 0.98583 | 22.055 | N/A | INT8_PATH_BLOCKED | FP32 baseline retained |

The Scope 21 FP32 NCNN baseline remains valid. Scope 22 does not choose between FP32, another backend, or a 320 experiment; Research & Design must decide the next path.
