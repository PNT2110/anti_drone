# Scope 29 — Pi Performance (Scope 29R)

Hardware: Raspberry Pi 5 Model B Rev 1.0, aarch64, NCNN FP32, 4 threads. Offline Scope 28 reference is 22.7375 FPS; live sustained processing was 21.5691 FPS.

| Metric | Value |
|---|---|
| Smoke total latency | 46.2232 mean / 54.0135 p95 ms |
| Sustained total latency | 46.3003 mean / 53.7595 p95 ms |
| Sustained capture-to-result | 86.0276 mean / 99.8468 p95 ms |
| Sustained capture FPS | 25.7560 |
| Sustained processing FPS | 21.5691 |
| Peak RSS | 146864 |
| Temperature | temp=49.9'C -> temp=60.4'C |
| Throttling | 0x0 -> 0x0 |

Inference ran once per captured frame and NMS once per inference. Queue stale drops are counted, not hidden.
