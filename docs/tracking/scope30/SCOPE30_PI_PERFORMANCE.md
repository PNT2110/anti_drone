# Scope 30 — Pi Performance

| Metric | Value |
|---|---|
| Camera source | /dev/video0, 640x480 MJPG requested 25 FPS |
| Capture / processing FPS | 25.7508 / 21.4716 |
| Total latency mean/p50/p95 | 46.3978 / 45.4398 / 54.2683 ms |
| Capture-to-result mean/p95 | 86.4121 / 100.7908 ms |
| Temperature | temp=41.7'C -> temp=53.2'C |
| Throttling | throttled=0x0 -> throttled=0x0 |
| Peak RSS | 133872 |

This performance result is operational live-camera evidence but not target-tracking accuracy or servo performance.

## Scope 30R2 / Attempt 3

No new performance run was started. The Scope 30 no-target and Scope 29R camera baselines remain unchanged.

## Scope 30R2 / Attempt 4 — Pi 5 target run

Capture/processing FPS: `25.7505/20.9649`. Total latency mean/p50/p95: `47.5204/46.4421/55.5524 ms`. Capture-to-result mean/p95: `86.3997/102.9029 ms`. Peak RSS: `135456 KB`; temperature: `temp=37.8'C -> temp=53.8'C`; throttling: `throttled=0x0 -> throttled=0x0`.
