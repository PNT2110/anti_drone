# Scope 19 — Final report

Status: **PARTIALLY_COMPLETE / BLOCKED FOR DEPLOYMENT FREEZE**.

Completed:

- Six Scope 18 checkpoints were hash-verified against the required values.
- Six float32 ONNX and six float32 NCNN artifacts were exported.
- Backend parity was evaluated with a predeclared tolerance on a deterministic train-only subset.
- Host CPU reference latency, FPS, and peak RSS were measured for ONNX and NCNN.
- Six TFLite float32 and six INT8 attempts were recorded honestly as blocked by the current Torch/LiteRT compatibility error.

Blocked/outstanding:

- No Raspberry Pi 5 is available in this workspace, so no Pi performance, thermal, RAM, or camera-I/O claim is made.
- No backend passed the strict all-eight-image parity gate.
- No INT8 artifact was produced.
- No production model is frozen; V3 test remains locked and `SPLIT_UNVERIFIED` is unchanged.

No retraining, tracker/gate change, threshold optimization, dataset reshuffle, test access, Pi/camera access, or Git commit/push was performed.

Reports: [input audit](SCOPE19_INPUT_AUDIT.md), [exports](SCOPE19_EXPORT_REPORT.md), [parity](SCOPE19_BACKEND_PARITY.md), [INT8](SCOPE19_INT8_REPORT.md), [Pi benchmark](SCOPE19_PI_BENCHMARK.md), [selection table](SCOPE19_MODEL_SELECTION_TABLE.md), [test report](SCOPE19_TEST_REPORT.md).

Runtime evidence is under `/run/media/pnt/APP/anti_drone/.runtime/scope19` and exported artifacts under `/run/media/pnt/APP/anti_drone/artifacts/exports/scope19`. Research & Design must review the parity failures and obtain real Pi 5 measurements before any deployment/model-selection freeze.
