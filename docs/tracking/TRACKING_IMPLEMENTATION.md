# Tracking implementation

## Scope

The detector remains the existing ONNX/NCNN/LiteRT pipeline. This change adds
the tracking and temporal-alert layer without changing training, datasets,
model architectures, export contracts, or Pi hardware configuration.

The runtime flow is:

```text
camera/replay frame
  -> monotonic/source timestamp
  -> letterbox + inference
  -> YOLO decode (confidence floor 0.10)
  -> xyxy validation and xyxy -> xywh NMS conversion
  -> high/low detection split
  -> first high-confidence association
  -> second low-confidence association
  -> Kalman prediction/update
  -> lifecycle state transition
  -> observation-only temporal alert
  -> overlay + JSONL runtime log
```

## Modules

- `src/anti_drone/tracking/types.py`: detection, track, and
  `TENTATIVE/CONFIRMED/LOST/REMOVED` state types.
- `association.py`: finite-box checks, IoU, center distance, and deterministic
  one-to-one assignment. Small scenes use an exact bitmask dynamic program;
  larger scenes use a deterministic sorted-pair fallback.
- `kalman.py`: constant-velocity state `[cx, cy, vx, vy, w, h]`, with actual
  timestamp delta in the transition and process noise.
- `bytetrack.py`: motion and motion-adaptive two-stage trackers.
- `bytetrack_legacy.py`: preserved pre-motion greedy IoU implementation,
  exposed as `ByteTrackLegacy` and the compatibility name `ByteTrackLite`.
- `src/anti_drone/alerts/temporal_alert.py`: per-track observation history,
  high-confidence count, time window, cooldown, session ID, and event ID.

## Important semantics

An unmatched track can still be returned for display as `PREDICTED`, but it is
not a temporal-alert observation. Only a detection matched in the current
source frame increments observation counts. Repeated source-frame IDs are
deduplicated. A capture timestamp is monotonic on camera runs; replay uses
`frame_id / --source-fps` so dropped source frames create a real time gap.

Track timeout is measured in seconds. A gap greater than
`max_gap_before_reset_seconds` clears stale motion state and starts IDs for a
new session. Explicit `reset()` is available for application-level reconnect
handling.
