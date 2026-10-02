# Scope 29 — Camera Discovery / Scope 29R Recovery

| Metric | Value |
|---|---|
| USB identity | Jieli Technology USB Composite Device |
| Vendor/Product | 4c4a:4a55 |
| Capture node | /dev/video0 |
| Metadata node | /dev/video1 |
| V4L2 probe | 250 consecutive frames PASS |
| Selected mode | MJPG 640x480 requested 25 FPS |
| Pi | Raspberry Pi 5 Model B Rev 1.0, aarch64 |
| OpenCV | 5.0.0 |

The camera advertises MJPG 640x480 at 25/30 FPS and YUYV 640x480 at 30 FPS. `/dev/video1` is metadata-only. Raw post-recovery discovery is `.runtime/scope29r/camera_discovery_raw.txt`.
