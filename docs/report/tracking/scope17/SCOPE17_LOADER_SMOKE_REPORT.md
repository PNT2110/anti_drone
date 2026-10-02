# Scope 17 — Loader Smoke Report

Script: `scripts/scope17_loader_smoke.py`; môi trường `/home/pnt/miniconda3/envs/antidrone`.

- Python `3.12.14`.
- Torch `2.8.0+cu129`; Ultralytics `8.4.125`; CUDA khả dụng.
- `data.yaml` parse PASS.
- Loader đọc train/val/test: 12.142 / 8.237 / 9.848.
- Tensor ảnh: `[3, 640, 640]`; sample train/val/test đều có class tensor `[1,1]`, bbox tensor `[1,4]`.
- YOLOv8n, YOLOv11n, YOLOv26n load PASS.
- Không chạy epoch, validation model selection hoặc test scoring.

Machine-readable result: `.runtime/scope17/loader_smoke.json`.
