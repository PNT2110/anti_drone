# Scope 23 — Host INT8 parity

Host parity status: **FAIL for all declared primary configurations**.

The FP32 reference was the existing Scope 19 NCNN FP32 artifact and the INT8 candidate was the freshly generated Scope 23 artifact. Both used the same exact preprocess and postprocess contract; detection confidence remained 0.25 and NMS IoU remained 0.70. The outputs include raw shape, candidate count, pre-NMS count, final detections, and gate metrics per image in `.runtime/scope23/experiments/E1/`, `E2/`, and `E3/`.

No host-pass artifact exists, so there is no authorized production candidate.
