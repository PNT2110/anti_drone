# Scope 30 — Live Target Run

Status: `LIVE_TARGET_TRACKING_BLOCKED`.

| Metric | Value |
|---|---|
| Declared duration | 90.026 s / 90.0 s |
| Captured / processed | 2316 / 1933 |
| Stale queue drops | 382 |
| Read failures / invalid frames | 0 / 0 |
| HIGH detection frames | 0 |
| LOW-only frames | 0 |
| Target observed / inferred / predicted / none | 0 / 0 / 0 / 1933 |
| Track IDs | [] |
| Target seen through webcam | False |

The session was run against the physical webcam only. No manual target alignment was available before the declared run; a snapshot showed the camera aimed at the ceiling.

## Scope 30R result

Attempt 2 stopped before the live run with `TARGET_ALIGNMENT_REQUIRED`; no 90-second session was run.

## Scope 30R2 / Attempt 3

No accepted live-target run was started. The run was stopped at the mandatory alignment snapshot gate with `TARGET_ALIGNMENT_REQUIRED`.

## Scope 30R2 / Attempt 4 — accepted 90-second run

{
  "status": "LIVE_TARGET_RUN_COMPLETE",
  "duration_s": 90.00761236299877,
  "captured": 2316,
  "processed": 1887,
  "stale_drops": 428,
  "read_failures": 0,
  "invalid_frames": 0
}
