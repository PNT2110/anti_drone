# Scope 24 — Input audit

Status: **frozen inputs PASS; alternate INT8 paths blocked**.

- Only `scope18-yolov8n-480` and `scope18-yolov8n-640` were evaluated.
- Scope 18 `best.pt`, Scope 20 FP32 parity, Scope 21 Pi FP32 evidence, Scope 22 artifacts, and Scope 23 conclusion were immutable baselines. No `last.pt` or TEST inference was used.
- Repaired V3 manifest SHA-256: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`.
- Repaired split registry SHA-256: `c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1`.
- Calibration: exact 128-image TRAIN membership, SHA-256 `4c582deab8ec13a23a0ecf0b1b806e6f3dd0c2c43f5a7dca06c785227e444b59`.
- Diagnostics: fixed 8 TRAIN images and frozen secondary 32 TRAIN images; `test_accessed=false`.
- Gates fixed before results: confidence `0.25`, NMS IoU `0.70`, count mismatch `0`, class mismatch `0`, min IoU `0.90`, max confidence shift `0.20`.

Frozen plans: [`tflite_plan.json`](../../../.runtime/scope24/tflite_plan.json) and [`ort_plan.json`](../../../.runtime/scope24/ort_plan.json).
