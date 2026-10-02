# Phase 00 — Repository baseline

Trạng thái: `TODO`

## Mục tiêu

Xác nhận repository, môi trường Python/GPU, cấu trúc thư mục và dữ liệu hiện có
trước khi thực hiện bất kỳ bước xử lý dataset nào.

## Phạm vi

Bao gồm kiểm tra hệ thống, dependency, CUDA, config, archive và test skeleton.

Không bao gồm giải nén dataset, train, export model hoặc chạy camera.

## Điều kiện đầu vào

- Root project: `/run/media/pnt/APP/anti_drone`.
- Có cấu trúc `configs/`, `data/`, `.runtime/`, `artifacts/`, `docs/`, `src/` và `tests/`.
- Các archive dữ liệu đã có trong `data/import_data_rar/`.

## Cấu hình sử dụng

- Python theo `pyproject.toml`.
- Environment train riêng cho máy GPU.
- Environment runtime riêng cho Pi, không dùng để train.
- Không sửa hoặc di chuyển archive gốc.

## Lệnh thực hiện

```bash
cd /run/media/pnt/APP/anti_drone

python --version
python -m pip --version
python -c "import sys; print(sys.executable)"

python - <<'PY'
import importlib.util
for name in ["torch", "ultralytics", "onnx", "yaml"]:
    print(name, bool(importlib.util.find_spec(name)))
PY

python - <<'PY'
try:
    import torch
    print("torch:", torch.__version__)
    print("cuda_available:", torch.cuda.is_available())
    print("cuda_version:", torch.version.cuda)
    if torch.cuda.is_available():
        print("gpu:", torch.cuda.get_device_name(0))
        print("gpu_count:", torch.cuda.device_count())
except Exception as exc:
    print("CUDA_CHECK_ERROR:", repr(exc))
PY

find configs docs src tests -maxdepth 3 -type f -print | sort
find data/import_data_rar -maxdepth 1 -type f -printf '%f %s bytes\n' | sort
find . -type f -name '*.crdownload' -print

python -m pytest -q
```

Nếu dependency chưa cài trên máy GPU:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

## Output bắt buộc

```text
.runtime/baseline/
├── system.json
├── python.json
├── cuda.json
├── repository.json
└── baseline_report.md
```

Các file JSON phải ghi command, timestamp, hostname, Python version, package
versions, GPU name, CUDA version và trạng thái command.

## Checklist

- [ ] Root project đúng.
- [ ] Python executable đúng environment.
- [ ] PyTorch import được.
- [ ] CUDA được nhận trên máy train.
- [ ] Cấu trúc project tồn tại.
- [ ] Archive được inventory, không bị ghi đè.
- [ ] File `.crdownload` được đánh dấu quarantine.
- [ ] Test skeleton chạy được hoặc đã ghi lỗi cụ thể.
- [ ] Baseline report đã sinh.

## Acceptance gate

Phase đạt khi Python, package và CUDA được xác nhận; dữ liệu tải dở không được
đưa vào train; test skeleton có kết quả; và `.runtime/baseline/baseline_report.md`
tồn tại.

## Dừng hoặc quay lại

- Dừng nếu không xác định được root project hoặc environment.
- Quay lại bước cài dependency nếu package import lỗi.
- Quay lại setup GPU nếu `torch.cuda.is_available()` là `False` trên máy train.
- Không chuyển Phase 01 nếu baseline report chưa hoàn tất.

## Provenance

Lưu command, exit code, timestamp, hostname, Git state nếu có, danh sách package,
GPU/CUDA và SHA-256 của các config chính.

