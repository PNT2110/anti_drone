# Scope 16 — Resource Preflight

Resource preflight chỉ đọc, không khởi động training. Artifact: `.runtime/scope16/resource_preflight.json`.

- Python: `3.12.14` trong `/home/pnt/miniconda3/envs/antidrone`.
- Torch: `2.8.0+cu129`; Ultralytics `8.4.125`; CUDA khả dụng.
- GPU: NVIDIA GeForce RTX 3060, 12,288 MiB; lúc kiểm tra khoảng 11,066 MiB free, utilization 0%.
- Không phát hiện training process cũ.
- Scope 15 có đủ sáu config và ba exact pretrained weights với hash đã khóa.
- Output root Scope 16 chưa tồn tại; không có nguy cơ overwrite run cũ.
- Test không được đọc bởi launcher vì label gate đã chặn trước launcher.

Resource gate không phải nguyên nhân chặn. Nguyên nhân duy nhất là `SCOPE16_LABEL_PREFLIGHT.md`.
