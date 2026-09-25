# Scope 20 — Final report

Status: **PARTIALLY_COMPLETE** — parity corrective work completed for intended ONNX and most NCNN paths; deployment freeze remains blocked.

Completed:

- Baseline audit PASS; all six Scope 18 `best.pt` hashes and all Scope 19 dataset/export hashes remain unchanged.
- Root cause found and reproduced: Scope 19 used incompatible PT/static-export letterbox behavior (`rect=True`); 48/48 locked comparisons had different preprocess tensors.
- Corrected harness uses one static `rect=False` contract. Eight ONNX pairs and four YOLOv8/YOLOv11 NCNN pairs pass the unchanged Scope 19 gate.
- YOLO26 NCNN is correctly retained as `PARITY_FAIL` because its `[1,5,N]` output contract is not equivalent to the `[1,300,6]` end-to-end contract.
- INT8 calibration provenance is complete for all six candidates; all full-integer attempts are recorded `INT8_BLOCKED` with exact environment and artifact evidence.
- Real Pi 5 access was checked and is `PI_BENCHMARK_BLOCKED` on x86_64.

Not complete:

- No real Pi 5 benchmark.
- No valid INT8 artifact or INT8 parity result.
- No production model freeze.
- V3 test remains locked; `SESSION_DISJOINT`/`SPLIT_UNVERIFIED` states are unchanged.

Reports: [input audit](SCOPE20_INPUT_AUDIT.md), [root cause](SCOPE20_PARITY_ROOT_CAUSE.md), [contract](SCOPE20_BACKEND_CONTRACT.md), [parity results](SCOPE20_PARITY_RESULTS.md), [INT8 environment](SCOPE20_INT8_ENVIRONMENT.md), [INT8 report](SCOPE20_INT8_REPORT.md), [Pi audit](SCOPE20_PI_INPUT_AUDIT.md), [Pi benchmark](SCOPE20_PI_BENCHMARK.md), [selection evidence](SCOPE20_MODEL_SELECTION_EVIDENCE.md), [tests](SCOPE20_TEST_REPORT.md).

Machine evidence: `/run/media/pnt/APP/anti_drone/.runtime/scope20`. New artifacts: `/run/media/pnt/APP/anti_drone/artifacts/exports/scope20`. No Git commit/push was performed.
