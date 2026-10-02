# V3 Loader Smoke Report

Script: `scripts/scope15_loader_smoke.py`. Chạy bằng `/home/pnt/miniconda3/envs/antidrone/bin/python`; kết quả **PASS**, không chạy epoch và không cập nhật weights.

- Python `3.12.14`.
- Ultralytics `8.4.125`.
- Torch `2.8.0+cu129`; CUDA khả dụng.
- `data.yaml` parse được và trỏ đúng candidate V3.
- Loader đọc train/val/test với độ dài 12,142 / 8,237 / 9,848, tensor ảnh `[3, 640, 640]`.
- YOLOv8n, YOLOv11n và YOLOv26n đều load thành công với task `detect`.
- Weight hashes được ghi trong `.runtime/scope15/loader_smoke.json`.

Ultralytics tạo label cache khi smoke test; cache chỉ là artifact loader trong candidate, không sửa ảnh/label nguồn.
