# Scope 01 tracking-only benchmark

## Method

Detector outputs were cached once using the real ONNX model and parity image
set:

```bash
python scripts/cache_detections.py \
  --runtime onnx --model artifacts/deploy/yolov8n/onnx/best.onnx \
  --input .runtime/parity-set \
  --output .runtime/scope01/detection-cache/onnx_parity_8frames.jsonl \
  --confidence 0.10 --nms-iou 0.70 --source-fps 30 --max-frames 8
```

The same cache was replayed through all three trackers:

```bash
python scripts/benchmark_tracking.py \
  --input .runtime/scope01/detection-cache/onnx_parity_8frames.jsonl \
  --output .runtime/scope01/benchmark/tracking_profiles.json
```

This measures tracking only; model inference and image decoding are excluded
from tracker latency. The cache has one sequence and eight frames. Hardware is
the local x86_64 host, Python 3.14.7, NumPy 2.5.3, and the temporary virtualenv
described in `SCOPE01_TEST_REPORT.md`.

## Results

| Profile | Frames | Sequences | Mean ms | P50 ms | P95 ms | P99 ms | Peak RSS delta KB | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `bytetrack_legacy` | 8 | 1 | 0.0171 | 0.0050 | 0.0519 | 0.0534 | 0 | DONE |
| `bytetrack_motion` | 8 | 1 | 0.0911 | 0.0481 | 0.2116 | 0.2287 | 1068 | DONE |
| `bytetrack_motion_adaptive` | 8 | 1 | 0.0556 | 0.0302 | 0.1407 | 0.1477 | 0 | DONE |

The complete machine-readable result is
`.runtime/scope01/benchmark/tracking_profiles.json`. RSS is a process-level
peak delta and is noisy for an eight-frame smoke run.

## Ground truth and interpretation

No identity ground truth was present in the detection cache. HOTA, IDF1, IDSW,
fragmentation, false-alert/hour, and time-to-alert are therefore `N/A`. The
latency table does not support a claim that one profile has better ID
retention. No thresholds were tuned against this input.

## Status

`PASS` for same-detection tracking benchmark generation. Pi hardware
benchmark and annotated identity-quality benchmark remain unavailable in this
environment.
