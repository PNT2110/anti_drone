# Scope 27 — Tracker discovery

The existing tracker implementation was reused unchanged:

- `src/anti_drone/tracking/bytetrack.py`: timestamp-aware two-stage ByteTrack with Kalman and Mahalanobis/center gating.
- `src/anti_drone/tracking/bytetrack_legacy.py`: preserved legacy implementation.
- `src/anti_drone/tracking/lifecycle.py`: confirmation/lost/removal lifecycle.
- `configs/trackers/bytetrack_motion_adaptive.yaml`: current default profile.
- `scripts/run_phase5.py`: existing replay/camera entry point.

`TRACKER_PROFILE_CURRENT = bytetrack_motion_adaptive`. Existing values were retained: detector floor `0.10`, low/high/new thresholds `0.10/0.25/0.35`, match IoU `0.30`, adaptive center gate `2.50`, Mahalanobis gate `25.0`, process/measurement noise `1.0/4.0`, confirmation `2`, max lost `0.60 s`, reset gap `1.00 s`.

No Kalman, association, lifecycle, profile YAML, autostart, camera, GPIO, PWM, or servo code was modified.
