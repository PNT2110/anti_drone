# Scope 19 — Raspberry Pi 5 benchmark

Status: **BLOCKED — NO RASPBERRY PI 5 IN WORKSPACE**.

The current host is `Linux-7.0.0-31-generic-x86_64-with-glibc2.43` / `x86_64`. No Pi 5, Pi camera, or live camera was accessed. The table below is CPU host reference data only; it must not be interpreted as Pi 5 throughput, power, thermal, or sustained-load evidence.

| Run | Runtime | Mean ms | P95 ms | Host FPS | Peak RSS MiB | Parity |
|---|---|---:|---:|---:|---:|---|
| `scope18-yolov8n-640` | `onnx` | 57.91 | 65.02 | 17.27 | 836.5 | `BACKEND_PARITY_FAIL` |
| `scope18-yolov8n-640` | `ncnn` | 37.02 | 40.13 | 27.01 | 889.1 | `BACKEND_PARITY_FAIL` |
| `scope18-yolov8n-480` | `onnx` | 32.12 | 42.92 | 31.14 | 858.0 | `BACKEND_PARITY_FAIL` |
| `scope18-yolov8n-480` | `ncnn` | 22.18 | 24.89 | 45.08 | 868.0 | `BACKEND_PARITY_FAIL` |
| `scope18-yolov11n-640` | `onnx` | 51.61 | 60.14 | 19.38 | 910.9 | `BACKEND_PARITY_FAIL` |
| `scope18-yolov11n-640` | `ncnn` | 39.56 | 42.92 | 25.28 | 918.3 | `BACKEND_PARITY_FAIL` |
| `scope18-yolov11n-480` | `onnx` | 30.92 | 43.05 | 32.34 | 938.3 | `BACKEND_PARITY_FAIL` |
| `scope18-yolov11n-480` | `ncnn` | 23.45 | 25.78 | 42.64 | 919.3 | `BACKEND_PARITY_FAIL` |
| `scope18-yolo26n-640` | `onnx` | 36.68 | 42.41 | 27.26 | 959.1 | `BACKEND_PARITY_FAIL` |
| `scope18-yolo26n-640` | `ncnn` | 39.18 | 42.12 | 25.52 | 946.9 | `BACKEND_PARITY_FAIL` |
| `scope18-yolo26n-480` | `onnx` | 24.29 | 31.55 | 41.17 | 916.0 | `BACKEND_PARITY_FAIL` |
| `scope18-yolo26n-480` | `ncnn` | 22.90 | 25.02 | 43.67 | 907.8 | `BACKEND_PARITY_FAIL` |

Each record uses 20 warm-up passes per image and 100 measured predictions over the fixed 8-image `train` subset. Pi 5 measurements, thermal behavior, and camera I/O remain outstanding.
