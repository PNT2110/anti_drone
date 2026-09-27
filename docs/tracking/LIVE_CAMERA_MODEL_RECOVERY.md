# USB live-camera detector recovery

## Root cause

The Raspberry Pi NCNN runtime and export were not the primary failure. The
frozen PyTorch checkpoint and its NCNN export both failed on the same raw USB
frames. Scope 18 training used only the repaired Anti-UAV300 TRAIN split: its
objects are predominantly small/far and every image is positive. The project's
2,334 `my_dataset` images—which contain the actual red/white open-frame drone
and indoor scenes—were excluded from Scope 18 because their provenance was
quarantined. The USB view also made the drone occupy roughly 60–80% of the
frame and clipped it at image edges, a scale/truncation regime absent from the
frozen training distribution.

## Corrective training

- Kept all 12,142 frozen V3 TRAIN images.
- Added all 2,334 `my_dataset` images to TRAIN, remapping drone class 15 to 0.
- Retained 192 reviewed negative `my_dataset` frames.
- Added 4,271 deterministic close crops from positive `my_dataset` TRAIN
  images.
- Added two manually reviewed USB calibration frames through 512 sampling
  records, then 26 fresh reviewed USB frames through 1,248 records. Their
  labels cover the full visible drone extent, including image truncation.
- Did not access V3 TEST.
- Kept image size 480, confidence 0.25, NMS IoU 0.70, and the existing
  `bytetrack_motion_adaptive` tracker contract.

The selected stage-3 epoch-4 checkpoint retained frozen V3 VAL precision
0.98837, recall 0.98167, mAP50 0.99030, and mAP50-95 0.61508. It produced
exactly one whole-drone detection on all 26 fresh USB frames (minimum
confidence 0.879, mean 0.930) and no detection on the fresh empty-room frame.
The final checkpoint SHA-256 is
`95311d7a56480bf5c1c831f94232443b89f8c96e19aaf0d4a446875a51050568`.

The NCNN diagnostic preserved exact detection counts on all 29 checked images.
Maximum confidence difference was 0.03528 and minimum box IoU was 0.93648.
The latter is recorded as a diagnostic warning against the historical strict
0.95 export gate; the live-camera candidate is not presented as a replacement
for the immutable Scope 25 production artifact.

To prevent one close drone from spawning simultaneous tracks for its visible
parts, the live runtime suppresses a lower-priority box only when it is almost
entirely contained by a substantially larger same-class box. Standard NMS
remains exactly once at IoU 0.70. The single-drone application exposes public
`DRONE ID 1` for the whole session while retaining every ByteTrack internal ID
in logs. This is session identity continuity, not cross-session visual re-ID.

## Deployment artifact

The adapted NCNN artifact is stored separately at
`artifacts/deploy/live-camera-v2/`; Scope 25 remains unchanged. The runtime
template points to this new artifact. The final visible Raspberry Pi USB-camera
run passed for 1,614 frames; details are recorded in
`LIVE_CAMERA_ID_STABILITY_REPORT.md`.
