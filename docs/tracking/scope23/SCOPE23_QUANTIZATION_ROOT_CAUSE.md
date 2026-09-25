# Scope 23 — Quantization root cause

Scope 22 used `ncnn2table` on raw images with direct resize to the target shape. Scope 21 inference uses BGR input converted to RGB, `rect=False` letterbox padding 114, float32 normalization by `/255`, and NCHW tensor order. This is a real calibration-contract mismatch and was the first corrective hypothesis.

Scope 23 E1/E2 replaced the raw-image calibration representation with exact Scope 21 preprocessed NCHW float32 NPY tensors (`type=1`). E3 kept that representation and changed only the officially supported quantizer method from KL to ACIQ. The mismatch did not disappear: the first divergence remains quantized model behavior after PTQ, not an unexamined confidence-threshold change.

Observed evidence:

- E1 (KL, 128 exact runtime tensors): v8n-480 fixed count mismatch 7/8, min IoU 0.677969; v8n-640 3/8, min IoU 0.757873.
- E2 (KL, 256 exact runtime tensors): v8n-480 8/8 and v8n-640 4/8 count mismatches.
- E3 (ACIQ, 128 exact runtime tensors): v8n-480 1/8, min IoU 0.820101; v8n-640 1/8, min IoU 0.850118. Both still fail the zero-count-mismatch and IoU >= 0.90 gates; secondary-32 also fails.

This does not prove that every possible NCNN PTQ configuration fails. It proves that the three predeclared, tool-supported and bounded configurations failed. No tolerance was relaxed, no threshold was tuned, and no postprocess was changed to conceal the failure.
