# Scope 30 — Input Audit

| Metric | Value |
|---|---|
| Scope 29R | USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY |
| Freeze manifest | e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964 PASS |
| Scope 26 headline | 7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83 PASS |
| NCNN param/bin | PASS |
| Detector | YOLOv8n-480 NCNN FP32 |
| HIGH / LOW | >=0.25 / 0.10–<0.25 |
| NMS | IoU 0.70, once per inference |
| Tracker | bytetrack_motion_adaptive |
| V3 TEST | not accessed |
| Actuation | disabled |

The frozen artifacts and Scope 29R recovered-camera evidence were verified before the target-presence attempt.
