# Scope 27 — Pi performance

Hardware: Raspberry Pi 5 Model B Rev 1.0, `aarch64`, 4 GiB-class RAM, NCNN `1.0.20260526`, 4 threads. Temperature was `39.5'C → 49.4'C`; throttling remained `0x0 → 0x0`.

| Stage | Mean ms | P50 ms | P95 ms |
|---|---:|---:|---:|
| Decode/read | 0.768 | 0.714 | 0.771 |
| Preprocess | 1.996 | 1.991 | 2.047 |
| Detector inference | 36.462 | 36.434 | 36.725 |
| Detector postprocess | 4.791 | 4.788 | 4.899 |
| Tracker update | 0.463 | 0.525 | 0.690 |
| Target selection | 0.006 | 0.006 | 0.006 |
| Total pipeline | 44.542 | 44.473 | 44.886 |

Effective sequential processing rate: **22.451 FPS**. This is an offline video-file processing rate, not a webcam FPS claim. Detector-only Scope 25R short smoke was approximately 23.12 FPS; the measured adapter/tracker overhead is separated above.
