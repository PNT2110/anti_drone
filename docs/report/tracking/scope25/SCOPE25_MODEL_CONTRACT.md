# Scope 25 — Frozen model contract

Candidate: `scope18-yolov8n-480:ncnn`.

- Backend: NCNN FP32, version `1.0.20260526`, 4 threads.
- Input: OpenCV BGR → RGB → `rect=False` letterbox, padding `114`, fixed `480×480`, float32 `/255`, NCHW, batch 1.
- Output: `[1,5,N]`, `xywh` plus single-class confidence, class `0`.
- Confidence threshold: `0.25`.
- External NMS: exactly once, IoU `0.70`.
- INT8 status: `PTQ_INT8_PATHS_EXHAUSTED_FOR_CURRENT_SCOPE`.

Canonical copies of these contracts are in the production package and are hash-bound by the freeze manifest.
