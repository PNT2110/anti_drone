# Scope 27 — Input audit

Status: **PASS**.

- Scope 25 freeze manifest: `e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964` — verified.
- Scope 26 headline result: `7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83` — verified.
- Detector: `scope18-yolov8n-480:ncnn`, NCNN FP32, 480, confidence `0.25`, NMS IoU `0.70`.
- NCNN param/bin hashes: exact frozen hashes.
- Current tracker profile: `bytetrack_motion_adaptive`.
- Diagnostic source: Halmstad `V_DRONE_001.mp4`, 301 frames, 30 FPS, 640×512.
- Identity validation: PASS; one verified drone track.
- V3 TEST used for tuning: `false`.
- Physical actuator enabled: `false`.

The repository has no file/module literally named `pi5_servo_tracker`; the current implementation tree is `scripts/run_phase5.py` → `anti_drone.runtime.DetectorPipeline` → `anti_drone.tracking`.
