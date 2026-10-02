# Scope 23 — Final report

## Decision

**NCNN_INT8_PTQ_BLOCKED**. Scope 23 is complete for the bounded investigation but not complete for deployment or freeze review.

## Evidence

- Root cause identified: Scope 22 calibration used raw direct-resize images while Scope 21 runtime used exact letterbox/RGB/NCHW preprocessing. The corrected tensor calibration contract was tested.
- E1 KL/128 exact tensors: FAIL.
- E2 KL/256 exact tensors: FAIL.
- E3 ACIQ/128 exact tensors: FAIL; strongest bounded result, but still count and IoU gate failures on both primary candidates and secondary diagnostics.
- No v8 method passed, so YOLOv11n-480 secondary confirmation was correctly not run.
- No artifact was transferred to Pi, no INT8 Pi benchmark was reported, and no production model was frozen.

## Preserved boundaries

V3 TEST remains locked. `SESSION_DISJOINT` and `SPLIT_UNVERIFIED` remain unchanged. Scope 18 checkpoints, Scope 19 FP32 exports, Scope 21 FP32 Pi evidence, and Scope 22 artifacts were not overwritten. No retraining, threshold tuning, dataset/split change, tracker change, live camera access, Git commit, or Git push occurred.

Machine-readable outputs: [`experiment_summary.json`](../../../.runtime/scope23/experiment_summary.json) and [`artifact_checksums.json`](../../../.runtime/scope23/artifact_checksums.json).
