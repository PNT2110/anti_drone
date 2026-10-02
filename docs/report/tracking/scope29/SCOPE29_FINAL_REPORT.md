# Scope 29 — Final Report / Scope 29R Recovery

Initial Scope 29 status: `CAMERA_RUNTIME_BLOCKED`.

Scope 29R final status: `USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY`.

| Metric | Value |
|---|---|
| Physical recovery | User-reported webcam reconnect/power-cycle; post-recovery identity verified |
| USB identity/node | Jieli Technology USB Composite Device 4c4a:4a55 / /dev/video0 |
| V4L2 pre-application | PASS — 250 consecutive MJPG frames |
| Mode | MJPG 640x480 requested 25 FPS |
| Frozen hashes | All unchanged |
| HIGH parity | 8/8 PASS |
| Smoke | 60.03s; 1544/1293 captured/processed; drops=250; read/invalid=0/0 |
| Sustained | 600.02s; 15452/12942; stale=2509; read/invalid=0/0 |
| Capture/processing FPS | 25.7560 / 21.5691 |
| Latency mean/p95 | 46.3003/53.7595 ms |
| Capture age mean/p95 | 86.0276/99.8468 ms |
| Peak RSS/memory trend | 146864 KB; bounded/plateaued |
| Temperature/throttling | temp=49.9'C -> temp=60.4'C; 0x0 -> 0x0 |
| Target smoke | Not performed; no safe target present |
| Actuation/autostart | 0/0/0 writes; none |
| Scope26 headline | Unchanged |
| V3 TEST | Locked/not accessed |

The corrected live pipeline is now validated as dry-run ready. Stop here; do not enable servo and do not start Scope 30 automatically.
