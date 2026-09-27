# Scope 29 — Final Report

Final status: `CAMERA_RUNTIME_BLOCKED`

| Metric | Value |
|---|---|
| USB camera/device | /dev/video0 — Jieli Technology USB Composite Device |
| Selected format/resolution/FPS | MJPG, 640x480, requested 25 FPS |
| Parity smoke | 8/8 PASS; max conf diff 0.001234353; min bbox IoU 0.971743339 |
| Accepted short smoke | 45.05 s preliminary evidence; 1155 captured / 991 processed / 163 stale drops |
| Final sustained run | Not accepted; camera runtime became unstable/blocked after corrective iterations |
| Frozen detector hashes | UNCHANGED |
| Scope 28 dual stream | RETAINED |
| Scope 26 headline | UNCHANGED |
| Physical writes | 0 GPIO / 0 PWM / 0 serial |
| Autostart | None |
| V3 TEST | Not accessed |

The live integration code is implemented with bounded queue, explicit drop accounting, monotonic timestamps, source-frame validation, one NCNN inference/one NMS, Scope 28 HIGH/LOW streams, and dry-run target preview. However, the final live gate cannot be called READY because the USB camera did not remain reliable through the final validation sequence; V4L2 streaming also failed to complete a short probe. No model, tracker, threshold, or test artifact was changed to compensate.

Required user action: reconnect or power-cycle the USB webcam and rerun the Scope 29 command. Do not start Scope 30 automatically.
