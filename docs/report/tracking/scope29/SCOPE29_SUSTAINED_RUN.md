# Scope 29 — Final Sustained Run (Scope 29R)

Status: `LIVE_SUSTAINED_COMPLETE`; duration `600.024` seconds.

| Metric | Value |
|---|---|
| Captured / processed | 15452 / 12942 |
| Stale queue drops | 2509 |
| Read failures | 0 |
| Invalid dimensions | 0 |
| Processing skips/display drops | 0 / 0 |
| Capture FPS | 25.7560 |
| Processing FPS | 21.5691 |
| Total latency mean/p95 | 46.3003/53.7595 ms |
| Capture-to-result mean/p95 | 86.0276/99.8468 ms |
| Peak RSS | 146864 |
| Temperature | temp=49.9'C -> temp=60.4'C |
| Throttling | throttled=0x0 -> throttled=0x0 |
| Row-level bad resolutions | 0 |

Telemetry sample policy is bounded rolling 2048. RSS rose during startup and then plateaued around 146.8 MB; no unbounded memory growth was observed in the accepted 10-minute run. Every logged processed row was 640x480.
