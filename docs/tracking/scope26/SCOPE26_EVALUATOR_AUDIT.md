# Scope 26 — Evaluator audit

Primary result provenance is separated as required:

1. **NCNN inference:** the frozen Scope 25 NCNN package ran on the Raspberry Pi 5 using NCNN `1.0.20260526`, 4 threads.
2. **Frozen decode/postprocess:** `[1,5,N]` → `xywh` plus class-0 confidence; 0.25 threshold; external NMS IoU 0.70 exactly once.
3. **GT loader:** V3 label-repair candidate TEST labels, one class (`drone`, class 0), converted from normalized YOLO coordinates to source pixels.
4. **Matching:** deterministic per-image greedy one-to-one matching at IoU 0.50 for threshold Precision/Recall/F1 and error counts.
5. **Metric aggregation:** 101-point interpolated AP over the NCNN detections retained at the frozen confidence floor; AP at IoU 0.50 through 0.95 in 0.05 steps.

The primary result does not call `best.pt`, PyTorch, ONNX, INT8, or any alternate candidate. Predictions are stored in [`predictions.jsonl`](../../../.runtime/scope26/predictions.jsonl). Below-threshold raw candidates and pre-NMS candidates were not retained, so those two error causes are reported as not observable rather than inferred.
