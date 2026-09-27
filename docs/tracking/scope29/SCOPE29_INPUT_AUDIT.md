# Scope 29 — Input Audit

Status: `INPUTS_VERIFIED`; initial live status: `CAMERA_RUNTIME_BLOCKED`; Scope 29R recovery status: `USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY`.

| Metric | Value |
|---|---|
| Scope 25 freeze SHA-256 | e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964 |
| Scope 26 headline SHA-256 | 7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83 |
| NCNN param SHA-256 | 8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5 |
| NCNN bin SHA-256 | 23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7 |
| Scope 28 high equivalence | 301/301 PASS |
| Scope 29 pre-live parity | 8/8 PASS |
| Tracker profile | bytetrack_motion_adaptive |
| V3 TEST accessed | False |
| Actuator enabled | False |

The frozen detector, Scope 28 dual-stream adapter, and tracker config were verified before the camera run. No production package or TEST artifact was modified.

## Scope 29R closeout annotation

The `CAMERA_RUNTIME_BLOCKED` value above is historical evidence from the initial Scope 29 attempt. After the user-reported webcam reconnect/power-cycle, Scope 29R re-enumerated the same Jieli device, passed the bounded V4L2 probe, passed 8-image HIGH parity, and completed the accepted live smoke and sustained runs. The authoritative recovered result is `USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY`; the original blocked report remains preserved in `SCOPE29_INITIAL_FINAL_REPORT.md`.
