# Live USB-camera detection and ID stability

## Outcome

The stage-3 NCNN detector was verified on the Raspberry Pi 5 USB camera. The
annotated output showed one whole-visible-drone box labelled `DRONE ID 1`.
The verification ran for 1,614 frames: 1,604 were `OBSERVED`, 10 were initial
or reassociation `NO_TARGET` frames, and no frame used a prediction-only target.
The effective end-to-end display rate was 15.2592 FPS. Temperature after the
run was 51.6 C and `get_throttled` returned `0x0`.

## Why multiple IDs appeared before

The detector sometimes emitted a large whole-drone box plus nested boxes for
visible parts. Standard NMS at 0.70 correctly retained some of those boxes
because containment and IoU are different properties. ByteTrack treated the
retained boxes as different observations and could create multiple short-lived
motion-track IDs. It could also assign a new internal ID after motion exceeded
the existing association gate.

The correction has two independent parts:

1. A same-class containment guard removes a smaller box only when at least 88%
   of it lies inside a box at least 1.35 times larger and the larger box has
   sufficient confidence. Standard NMS remains exactly once at IoU 0.70.
2. The one-drone application now exposes the stable session identity
   `DRONE ID 1`. ByteTrack's internal ID remains logged as
   `tracker_target_id`, including reassociation changes, so diagnostics are not
   hidden. This is not multi-drone ReID or identity persistence across process
   restarts.

During the final live run ByteTrack used internal target IDs 1, 2, 3, and 5
with three reassociations, while the only public target ID was 1. The display
never showed the internal IDs and drew only the selected observed target.

## Frozen runtime values

- Model: YOLOv8n-480, NCNN FP32 stage-3 epoch 4.
- NCNN param SHA-256:
  `8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5`.
- NCNN bin SHA-256:
  `9f36f35538e9ec10074f09279a94829ea82fb8b41a75e86091008a3885ce60eb`.
- Detector confidence: 0.25.
- Tracker low floor: 0.10.
- NMS IoU: 0.70, exactly once.
- Tracker profile: `bytetrack_motion_adaptive`.
- USB camera: MJPG, 640x480, 25 FPS request.
- Physical servo output during verification: disabled.
- V3 TEST accessed: no.
