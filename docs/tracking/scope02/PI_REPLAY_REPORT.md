# Scope 02 replay report

## Pi status

Offline replay on the actual Raspberry Pi is `BLOCKED — PI HARDWARE ACCESS`.
No SSH, camera, or remote package installation was performed.

## Host integration replay

As a local preparation and compatibility check, the current pipeline ran the
existing `.runtime/parity-set` (8 repository images) with the existing 640
ONNX and NCNN exports. All runs used input size 640, detector confidence 0.10,
NMS IoU 0.70, 30 FPS replay timestamps, and the same image order.

| Runtime/profile | Frames | Track rows | Alerts | Mean end-to-end ms | Max ms | Valid boxes/logs |
|---|---:|---:|---:|---:|---:|---|
| ONNX / legacy | 8 | 3 | 0 | 26.01 | 38.19 | PASS |
| ONNX / motion | 8 | 3 | 0 | 35.29 | 42.68 | PASS |
| ONNX / adaptive | 8 | 3 | 0 | 24.61 | 31.19 | PASS |
| NCNN / legacy | 8 | 3 | 0 | 38.99 | 47.00 | PASS |
| NCNN / motion | 8 | 3 | 0 | 40.66 | 59.07 | PASS |
| NCNN / adaptive | 8 | 3 | 0 | 53.38 | 90.35 | PASS |

These are x86_64 host measurements only. They are not Pi latency or FPS
claims.

## Temporal-data limitation

The eight files are a parity image set, not a continuous temporal sequence.
They contain mixed resolutions and unrelated frames. The pipeline correctly
resets on frame-shape changes, and logs contain monotonic replay timestamps,
valid positive IDs, observed/predicted labels, and alert metadata when events
exist. This validates integration behavior but is insufficient to evaluate
long-term ID retention or temporal tracking quality.

## Artifacts

```text
.runtime/scope02/replay/onnx/<tracker>/
.runtime/scope02/replay/ncnn/<tracker>/
```

Each profile directory contains annotated images, `environment.json`,
`runtime.log`, and `replay_report.json`.
