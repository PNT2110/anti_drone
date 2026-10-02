# Scope 18 — Resume/OOM report

The launcher permits fallback only after an actual OOM, keeps each attempt in a unique directory, and does not resume from `best.pt`. Resume is allowed only from an exact-run `last.pt` contract (run/model/imgsz/dataset/seed/effective batch).

| Run | Attempt | Batch | Status | Duration (s) |
|---|---|---:|---|---:|
| scope18-yolov8n-640 | attempt-batch16 | 16 | COMPLETE | 9706.101668 |
| scope18-yolov8n-480 | attempt-batch16 | 16 | COMPLETE | 6136.708409 |
| scope18-yolov11n-640 | attempt-batch16 | 16 | COMPLETE | 9605.818749 |
| scope18-yolov11n-480 | attempt-batch16 | 16 | COMPLETE | 6436.987711 |
| scope18-yolo26n-640 | attempt-batch16 | 16 | COMPLETE | 10996.285101 |
| scope18-yolo26n-480 | attempt-batch16 | 16 | COMPLETE | 7448.432324 |

No OOM event was recorded; therefore no batch fallback or resume was needed.
