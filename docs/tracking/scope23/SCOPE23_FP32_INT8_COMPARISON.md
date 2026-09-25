# Scope 23 — FP32 versus INT8 comparison

The comparison is diagnostic only and uses the locked FP32 NCNN reference. E1–E3 outputs record per-image detection count, class agreement, bbox IoU, and confidence shift. The strongest bounded configuration was E3 ACIQ/128 exact runtime tensors, but it still had fixed-set count mismatch 1/8 for both v8 candidates; minimum bbox IoU was 0.820101 (480) and 0.850118 (640). Secondary-32 also failed, so these INT8 artifacts are not deployment-ready.

The FP32 Scope 21 Pi measurements remain unchanged and are not re-labeled as INT8 measurements.
