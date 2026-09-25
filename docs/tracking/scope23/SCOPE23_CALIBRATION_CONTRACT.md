# Scope 23 — Calibration contract

- Calibration membership: exact Scope 22 128-image TRAIN manifest for E1/E3; deterministic 256-image TRAIN superset for E2.
- Validation and TEST were not used.
- Input: BGR image → RGB, `rect=False` square letterbox, constant padding 114, float32 `/255`, NCHW, target size 480 or 640.
- NCNN table command: official `ncnn2table`, `shape=[W,H,3]`, `type=1`, `thread=4`.
- Methods evaluated: `kl` and `aciq`, both supported by the isolated NCNN toolchain at tag `20260526`.
- E0 Scope 22 raw-image KL result is retained as the diagnostic baseline only; it was not silently replaced.
- Thresholds fixed before results: confidence 0.25 and NMS IoU 0.70.

The exact NPY manifests and tensor statistics are in `.runtime/scope23/calibration_manifests/` and `.runtime/scope23/input_contract.json`.
