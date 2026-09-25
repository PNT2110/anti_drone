# Scope 19 — Model selection table

This is a deployment-readiness comparison, not a final production freeze. Accuracy values are frozen Scope 18 validation values; V3 test remains locked and is not used.

| Run | Frozen mAP50 | Frozen mAP50-95 | Frozen recall | Parameters | ONNX MiB | NCNN MiB | Host ONNX FPS | Host NCNN FPS | Host peak RSS MiB | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `scope18-yolov8n-640` | 0.99294 | 0.63360 | 0.98665 | 3,011,043 | 11.70 | 11.63 | 17.27 | 27.01 | 889.1 | `PARETO_CANDIDATE_PENDING_RESEARCH_DESIGN` |
| `scope18-yolov8n-480` | 0.99286 | 0.62836 | 0.98689 | 3,011,043 | 11.63 | 11.59 | 31.14 | 45.08 | 868.0 | `PARETO_CANDIDATE_PENDING_RESEARCH_DESIGN` |
| `scope18-yolov11n-640` | 0.99294 | 0.62983 | 0.98725 | 2,590,035 | 10.11 | 10.03 | 19.38 | 25.28 | 918.3 | `PARETO_CANDIDATE_PENDING_RESEARCH_DESIGN` |
| `scope18-yolov11n-480` | 0.99280 | 0.62466 | 0.98583 | 2,590,035 | 10.04 | 9.99 | 32.34 | 42.64 | 938.3 | `PARETO_CANDIDATE_PENDING_RESEARCH_DESIGN` |
| `scope18-yolo26n-640` | 0.99309 | 0.63170 | 0.98543 | 2,504,190 | 9.35 | 9.26 | 27.26 | 25.52 | 959.1 | `PARETO_CANDIDATE_PENDING_RESEARCH_DESIGN` |
| `scope18-yolo26n-480` | 0.99225 | 0.62691 | 0.98264 | 2,504,190 | 9.28 | 9.21 | 41.17 | 43.67 | 916.0 | `PARETO_CANDIDATE_PENDING_RESEARCH_DESIGN` |

Selection policy: retain recall and mAP50-95, require export and backend parity, consider parameters/RAM/runtime, and require real Pi 5 evidence before deployment freeze. FLOPs are `N/A` because the framework did not expose a machine-readable value through this harness. Decision: **NO_MODEL_FROZEN_WITHOUT_PI5_EVIDENCE**.
