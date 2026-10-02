# Tracking configuration

The CLI supports three profiles through `--tracker`:

| Profile | Association | Intended use |
|---|---|---|
| `bytetrack_legacy` | Greedy IoU, legacy frame-count timeout | rollback/ablation |
| `bytetrack_motion` | high/low ByteTrack + Kalman + fixed IoU gate | baseline motion tracker |
| `bytetrack_motion_adaptive` | motion tracker plus normalized center-distance fallback | default for small drones |

Reference YAML profiles live in `configs/trackers/`. The current CLI exposes
the core values directly so a Pi run is reproducible from `environment.json`:

```bash
python scripts/run_phase5.py replay \
  --runtime onnx --model artifacts/model.onnx --input replay/images \
  --output runs/tracking-adaptive \
  --tracker bytetrack_motion_adaptive \
  --confidence 0.10 --track-low-thresh 0.10 \
  --track-high-thresh 0.25 --new-track-thresh 0.35 \
  --max-lost-seconds 2.50 --max-gap-before-reset-seconds 1.00
```

Default thresholds are detector floor `0.10`, low association `0.10`, high
association `0.25`, and new-track creation `0.35`. They are validated so the
ordering is `floor <= low < high <= new <= 1`.

The default profile keeps confirmed identities in `LOST` for 2.50 seconds and
stores up to eight trusted appearance descriptors per track. Normal matching
uses motion plus appearance when a quality-gated descriptor exists; LOST-track
resurrection uses a stricter ReID distance threshold (`0.34`) and a loose
normalized center gate (`8.0`). Appearance is updated only for crops with
quality `>= 0.45`; low-quality or ambiguous detections can move a track but
cannot rewrite its identity gallery.

Temporal alerts default to three observations, two high-confidence
observations, a 0.60-second confirmation window, and a two-second per-track
cooldown. Alert JSON events include a session ID and unique event ID.

`runtime.log` contains source and processing frame IDs, timestamp, latency,
track state, matched/observed/predicted status, box, confidence, observation
count, recovery count, occlusion risk, appearance-gallery size, and alert
events. `environment.json` records the selected tracker and thresholds.
