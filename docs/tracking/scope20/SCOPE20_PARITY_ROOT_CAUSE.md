# Scope 20 — Parity root cause

## Root cause A — Scope 19 harness preprocessing mismatch

The Scope 19 wrapper passed the default `rect=True`. For a PyTorch model, Ultralytics permits stride-minimal automatic padding; for a static ONNX/NCNN graph, the wrapper forces the square graph input. On the locked 6 models × 8 images, this reproduced a preprocess tensor mismatch in **48/48** comparisons.

The corrective harness forces `rect=False` for every backend and uses the same static 480/640 contract. It does not change confidence, IoU, model weights, or the acceptance gate.

## Root cause B — YOLO26 NCNN output contract

YOLOv8n/YOLOv11n exports expose `[1, 5, N]` (`xywh` plus one-class score; external NMS). YOLO26 PyTorch/ONNX expose `[1, 300, 6]` (`xyxy`, confidence, class; end-to-end top-k/NMS embedded). YOLO26 NCNN exposes `[1, 5, N]`, so it is not contract-equivalent to its PyTorch/ONNX end-to-end graph. It remains `PARITY_FAIL`/diagnostic-only. Passing `nms=True` to the NCNN exporter was explicitly rejected by Ultralytics as unsupported; no replacement export was silently substituted.

Raw tensors, representative rows, decoded tensors, final detections, per-image stage labels, and preprocess hashes are in `/run/media/pnt/APP/anti_drone/.runtime/scope20/parity_trace.json`.
