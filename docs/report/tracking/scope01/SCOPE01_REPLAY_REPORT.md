# Scope 01 replay report

## Input and model

The replay used artifacts already present in the repository; nothing was
downloaded or substituted:

- Model: `artifacts/deploy/yolov8n/onnx/best.onnx`
- Input: `.runtime/parity-set`, 8 existing images
- Runtime: ONNX Runtime CPU
- Input size: 640
- Detector confidence: 0.10
- NMS IoU: 0.70
- Replay FPS clock: 30 FPS
- Trackers: legacy, motion, motion-adaptive

Each profile used the same model, image order, input size, confidence, NMS
threshold, and source timestamp formula. Output artifacts are stored without
overwriting previous runtime evidence:

```text
.runtime/scope01/replay_hardened/onnx/bytetrack_legacy/
.runtime/scope01/replay_hardened/onnx/bytetrack_motion/
.runtime/scope01/replay_hardened/onnx/bytetrack_motion_adaptive/
```

Each directory contains `environment.json`, `runtime.log`,
`replay_report.json`, and annotated output images.

## Results

| Profile | Frames | Track rows | Alerts | Mean end-to-end ms | Max ms | Status |
|---|---:|---:|---:|---:|---:|---|
| `bytetrack_legacy` | 8 | 3 | 0 | 31.89 | 35.05 | DONE |
| `bytetrack_motion` | 8 | 3 | 0 | 29.06 | 34.71 | DONE |
| `bytetrack_motion_adaptive` | 8 | 3 | 0 | 24.11 | 28.90 | DONE |

The mixed-resolution parity set exposed an integration defect in the first
Scope 01 run: predicted coordinates from a 1920x1080 frame were retained when
the next frame was 640x512. The first-run evidence remains under
`.runtime/scope01/replay/onnx/`. The fix resets the pipeline when frame shape
changes and clamps only overlay/log display boxes; the hardened replay reports
valid in-frame boxes for all three profiles.

The hardened logs show timestamps increasing monotonically, positive track
IDs, explicit `observed` versus `predicted` status, and no alert events from
the short/mixed sequence. No false alert is claimed from this result.

## Status

`PASS` for local end-to-end replay. This is not a live camera or Raspberry Pi
acceptance run.
