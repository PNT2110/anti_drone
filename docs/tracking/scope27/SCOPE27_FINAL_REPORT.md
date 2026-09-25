# Scope 27 — Final report

## Final status

**`FROZEN_DETECTOR_TRACKER_DRYRUN_INTEGRATED`**

## Acceptance answers

- **Detector artifact/hash:** frozen YOLOv8n-480 NCNN FP32; param `8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5`, bin `23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7`.
- **Tracker/profile:** existing `ByteTrack` motion-adaptive implementation, `bytetrack_motion_adaptive`; no algorithm rewrite.
- **Diagnostic source:** Halmstad `V_DRONE_001.mp4`, 301 frames, 30 FPS, 640×512, diagnostic-only.
- **Frames:** 301 expected, 301 processed, no drops.
- **Detector observed:** 205 frames; no detection 96 frames.
- **Target state:** 204 observed, 41 predicted-only, 56 no-target frames.
- **Track IDs:** 1–5 created; 2 ID changes; 17 lost events; 16 reacquisition events; 3 target-selection changes.
- **Latency:** total pipeline mean/P95 `44.542/44.886 ms`; effective offline FPS `22.451`.
- **Memory/thermal:** Pi 5 4 GiB-class; available RAM approximately `3.71 GiB → 3.68 GiB`; temperature `39.5→49.4°C`; throttling `0x0→0x0`.
- **Actuator:** disabled; GPIO/PWM/serial writes all `0`; dry-run preview only.
- **Scope 26 headline:** unchanged at SHA-256 `7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83`.
- **Freeze manifest:** unchanged and verified at SHA-256 `e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964`.

The result is an integration characterization on one offline Halmstad sequence. It does not tune or select the detector/tracker, does not claim webcam performance, and does not prove session-independent generalization. `SESSION_DISJOINT` remains `UNVERIFIED`. No V3 TEST access was used for integration tuning, and no live camera/servo/actuator command was executed.
