# Scope 23 — Input audit

Status: **PASS for frozen inputs; PTQ result blocked**.

- Scope 18 `best.pt` baseline: re-checked through the Scope 20/21 audit; no checkpoint was modified and no `last.pt` was used.
- Repaired V3 dataset manifest SHA-256: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`.
- Repaired split registry SHA-256: `c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1`.
- Scope 22 calibration manifest SHA-256: `4c582deab8ec13a23a0ecf0b1b806e6f3dd0c2c43f5a7dca06c785227e444b59`; membership remained TRAIN-only.
- Scope 23 fixed set: 8 images from the locked Scope 19 benchmark manifest; secondary set: 32 deterministic TRAIN images.
- `test_accessed=false` in the Scope 23 plan and all experiment outputs.
- Primary candidates: NCNN YOLOv8n 480 and 640. YOLOv11n 480 was gated behind a passing v8 method and was therefore not run.
- Scope 21 Pi 5 FP32 evidence and Scope 22 FP32/INT8 baselines were retained; no Pi INT8 transfer was authorized after host failure.

The frozen plan is [`experiment_plan.json`](../../../.runtime/scope23/experiment_plan.json). The runtime input contract is [`input_contract.json`](../../../.runtime/scope23/input_contract.json).
