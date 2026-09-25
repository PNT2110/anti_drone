# Scope 22 — FP32 versus INT8 comparison

| Candidate | FP32 model MiB | INT8 model MiB | FP32 Pi FPS | INT8 Pi FPS | Speedup | FP32 peak RSS KiB | INT8 Pi RSS | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `scope18-yolov8n-480` | 11.585 | 2.971 | 22.493 | N/A | N/A | 225760 | N/A | HOST_INT8_RUNTIME_FAIL |
| `scope18-yolov8n-640` | 11.627 | 3.013 | 11.726 | N/A | N/A | 276896 | N/A | HOST_INT8_RUNTIME_FAIL |
| `scope18-yolov11n-480` | 9.992 | 2.589 | 22.055 | N/A | N/A | 185312 | N/A | HOST_INT8_RUNTIME_FAIL |

INT8 Pi columns are N/A because the host gate failed before transfer. Faster or smaller artifacts are not treated as improvements when diagnostic output is degraded.
