# Scope 21 — Real Raspberry Pi 5 FP32 benchmark

Status: **PASS**.

Each candidate used 20 warmup passes and 100 measured passes per fixed image, in fixed image order. Therefore each row contains 800 measured inferences. Preprocess, inference, postprocess, and end-to-end values are `mean / p50 / p95` in milliseconds; FPS is `1000 / end-to-end mean`.

| Run | Backend | Size | Model MiB | Load ms | Pre mean/p50/p95 | Inference mean/p50/p95 | Post mean/p50/p95 | E2E mean/p50/p95 | FPS | RSS idle/load/peak KiB | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `scope18-yolo26n-480` | onnx | 480 | 9.280 | 138.88 | 2.519 / 2.754 / 3.029 | 66.747 / 66.528 / 66.943 | 0.367 / 0.365 / 0.373 | 69.637 / 69.625 / 70.178 | 14.360 | 61712 / 100656 / 176080 | PI_BENCHMARK_PASS |
| `scope18-yolo26n-640` | onnx | 640 | 9.350 | 97.46 | 3.291 / 3.538 / 3.925 | 121.665 / 121.474 / 122.291 | 0.373 / 0.368 / 0.420 | 125.333 / 125.209 / 126.244 | 7.979 | 176080 / 176176 / 220576 | PI_BENCHMARK_PASS |
| `scope18-yolov11n-480` | ncnn | 480 | 9.992 | 48.92 | 2.198 / 2.278 / 2.496 | 38.205 / 38.183 / 38.497 | 4.934 / 4.934 / 5.017 | 45.341 / 45.394 / 45.742 | 22.055 | 220576 / 224544 / 185312 | PI_BENCHMARK_PASS |
| `scope18-yolov11n-480` | onnx | 480 | 10.043 | 89.39 | 2.477 / 2.784 / 2.878 | 73.433 / 73.394 / 73.807 | 4.921 / 4.926 / 4.994 | 80.836 / 80.888 / 81.493 | 12.371 | 185312 / 185312 / 229456 | PI_BENCHMARK_PASS |
| `scope18-yolov11n-640` | ncnn | 640 | 10.034 | 25.47 | 3.295 / 3.474 / 3.810 | 73.141 / 72.961 / 73.361 | 8.634 / 8.632 / 8.780 | 85.074 / 85.098 / 85.578 | 11.754 | 229456 / 229456 / 261616 | PI_BENCHMARK_PASS |
| `scope18-yolov11n-640` | onnx | 640 | 10.113 | 85.93 | 3.430 / 3.657 / 3.959 | 135.240 / 135.120 / 136.233 | 8.655 / 8.652 / 8.771 | 147.330 / 147.287 / 148.528 | 6.787 | 261616 / 261616 / 304192 | PI_BENCHMARK_PASS |
| `scope18-yolov8n-480` | ncnn | 480 | 11.585 | 29.45 | 2.083 / 2.247 / 2.298 | 37.443 / 37.416 / 37.647 | 4.927 / 4.927 / 5.025 | 44.458 / 44.514 / 44.810 | 22.493 | 304192 / 304192 / 225760 | PI_BENCHMARK_PASS |
| `scope18-yolov8n-480` | onnx | 480 | 11.627 | 58.78 | 2.468 / 2.743 / 2.808 | 77.756 / 77.726 / 78.046 | 4.901 / 4.899 / 4.976 | 85.129 / 85.246 / 85.687 | 11.747 | 225760 / 225760 / 237808 | PI_BENCHMARK_PASS |
| `scope18-yolov8n-640` | ncnn | 640 | 11.627 | 36.69 | 3.183 / 3.497 / 3.552 | 73.420 / 73.391 / 73.794 | 8.673 / 8.663 / 8.866 | 85.280 / 85.422 / 85.978 | 11.726 | 237808 / 237808 / 276896 | PI_BENCHMARK_PASS |
| `scope18-yolov8n-640` | onnx | 640 | 11.697 | 63.49 | 3.213 / 3.536 / 3.681 | 140.883 / 140.648 / 141.562 | 8.643 / 8.654 / 8.744 | 152.743 / 152.558 / 153.697 | 6.547 | 276896 / 276912 / 302624 | PI_BENCHMARK_PASS |

Hardware: `Raspberry Pi 5 Model B Rev 1.0`, `aarch64`, 4 GiB RAM. Temperature was `temp=51.0'C` before and `temp=73.0'C` after; throttling remained `throttled=0x0` to `throttled=0x0`. No camera, tracker, servo, or live targeting was used.
