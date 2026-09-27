# Scope 30R — Target Alignment Gate

Status: `TARGET_ALIGNMENT_REQUIRED`.

The single required pre-run webcam snapshot is `target_alignment_snapshot.jpg` with SHA-256 `6f426d45005780f158bb8de3b378997969709e9b099c63e3a0cca71ffcfc5636`. It is 640x480 and visibly contains ceiling/wall only. The monitor and Halmstad video are absent; approximate monitor coverage is 0%.

Per the Scope 30R gate, no 90-second target-present session was started. Required user action: physically aim the USB webcam at the monitor while `V_DRONE_001.mp4` is displayed, then rerun the one-snapshot gate.

## Scope 30R2 / Attempt 3

The new mandatory snapshot is `target_alignment_snapshot.jpg`, SHA-256 `8a73e64fa197dc16e4f7bd05cf47f9227834377e2fc6af4183a27764a961c1ce`. It is a fresh 640x480 frame from the physical `/dev/video0` webcam. Visual inspection shows ceiling/wall only: monitor visible = **no**, Halmstad video visible = **no**, approximate coverage = **0%**. Scope 30R2 therefore stopped with `TARGET_ALIGNMENT_REQUIRED` before the quick gate and before the accepted 90-second run.

## Scope 30R2 / Attempt 4 — PASS

Fresh snapshot SHA-256: `6da0e9d43ddbd4c3f02037fab44a781dcd83cf7ecaa4997b55273fd22cd8aa2d`. The monitor and Halmstad video were visibly present in the 640x480 webcam frame. Physical setup was held fixed for the accepted run.
