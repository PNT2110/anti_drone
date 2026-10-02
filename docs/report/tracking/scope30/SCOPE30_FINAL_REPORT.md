# Scope 30 — Final Report

Final status: `LIVE_TARGET_TRACKING_BLOCKED`.

| Metric | Value |
|---|---|
| Scope 29R final status | USB_WEBCAM_LIVE_TRACKING_DRYRUN_READY |
| Target source | Halmstad video displayed on HDMI monitor; physical webcam remained detector input |
| Target visible through physical webcam | False |
| Duration / captured / processed | 90.03s / 2316 / 1933 |
| HIGH / LOW-only frames | 0 / 0 |
| Track IDs / ID changes | [] / 0 |
| Lost / reacquired / predicted / none | 0 / 0 / 0 / 1933 |
| Error/command preview | No live target samples; software contract tests PASS |
| Camera failure safety | CAMERA_OPEN_FAILED |
| Servo discovery/bounds | No authoritative hardware config; SERVO_BOUNDS_UNKNOWN |
| Writes | 0 GPIO / 0 PWM / 0 serial / 0 servo / 0 motor |
| Performance | 21.4716 FPS; 46.3978 ms mean |
| Temperature/throttling | temp=41.7'C -> temp=53.2'C; throttled=0x0 -> throttled=0x0 |
| Scope 26 headline | 7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83 |
| V3 TEST | not accessed |
| Regression / compile / diff-check | 151 passed, 1 skipped / PASS / PASS |

The live target-presence acceptance gate is blocked because the webcam was aimed at the ceiling rather than the monitor target. This is `LIVE_TARGET_TRACKING_BLOCKED`, not a detector regression. Physical servo commissioning is independently blocked by unknown servo bounds. No Scope 31 was started.

## Scope 30R continuation

Attempt 1 remains `LIVE_TARGET_TRACKING_BLOCKED` because the camera saw the ceiling. Scope 30R attempt 2 captured exactly one snapshot and again found no monitor/video, so the current status is `TARGET_ALIGNMENT_REQUIRED`. No detector/tracker regression was inferred, no accepted target session was started, and no actuator was initialized.

Final Scope 30R regression: **154 passed, 1 skipped**; compileall PASS; `git diff --check` PASS. Scope 29R historical regression remains **145 passed, 1 skipped**.

## Scope 30R2 / Attempt 3

Current status: `TARGET_ALIGNMENT_REQUIRED`. The fresh snapshot SHA-256 is `8a73e64fa197dc16e4f7bd05cf47f9227834377e2fc6af4183a27764a961c1ce` and contains ceiling/wall only; monitor/video visibility is false. No accepted session was started, no detector/tracker conclusion was drawn, and no physical actuator was initialized. Scope 31 remains unopened.

Final Scope 30R2 regression: **157 passed, 1 skipped**; compileall PASS; `git diff --check` PASS.

## Scope 30R2 / Attempt 4 — final result

Current live-target status: `LIVE_TARGET_COMMAND_PREVIEW_READY`. The fresh alignment snapshot passed and the 90-second physical-webcam run produced target observations and non-neutral preview samples. Captured/processed: `2316/1887`; stale drops `428`; read/invalid `0/0`; HIGH/LOW-only `7/212`; IDs `[1, 2, 3]`; non-neutral preview `59`; rate-limit events `10`; neutral transitions `1828`; writes `0/0/0/0/0`.

Attempt 1–3 history is preserved. Scope 26 remains immutable and V3 TEST was not accessed. Physical servo commissioning remains `PHYSICAL_SERVO_COMMISSIONING_BLOCKED_BY_UNKNOWN_BOUNDS` despite the recorded channel mapping PAN GPIO13 / TILT GPIO12. Scope 31 was not started.

Final Attempt 4 regression: **158 passed, 1 skipped**; compileall PASS; `git diff --check` PASS.
