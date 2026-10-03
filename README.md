# anti_drone

Hệ thống thử nghiệm phát hiện và tracking drone một lớp bằng YOLO, kèm bảng điều khiển web (FastAPI) để phân tích video và camera. Repository này chỉ xử lý nhận diện, tracking và cảnh báo phần mềm; không điều khiển cơ cấu chấp hành hay vũ khí.

## Cấu trúc

```text
anti_drone/
├── web/                     # Bảng điều khiển web
│   ├── app.py               # FastAPI: REST, MJPEG, WebSocket
│   ├── security.py          # Xác thực bằng mật khẩu (tuỳ chọn)
│   ├── backend/             # config, detector, model_manager, tracker
│   ├── models/              # Checkpoint mà web được phép nạp
│   ├── static/, templates/  # Giao diện
│   ├── tests/               # pytest
│   ├── start.bat, stop.bat  # Chạy/dừng server + tunnel trên Windows
│   └── requirements*.txt
├── scripts/                 # Train ma trận model, hậu xử lý, đánh giá
├── configs/                 # Cấu hình dataset, model, tracker, training
├── models/                  # Model export (ONNX/NCNN) lưu tham chiếu
├── artifacts/               # Bundle triển khai, release, kết quả train
├── data/                    # Dataset — chỉ nằm trên đĩa, KHÔNG nằm trong git
└── docs/                    # description/, plan/, report/
```

`data/` không được theo dõi bằng git (xem `.gitignore`); chỉ các file `data.yaml` mô tả dataset được giữ lại. Không tự ý đổi tên, di chuyển hay xoá nội dung thư mục này.

## Cài đặt

Yêu cầu Python 3.12.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate
pip install -r web/requirements.txt
```

Máy có GPU nên cài PyTorch đúng phiên bản CUDA trước khi cài `web/requirements.txt`.

## Chạy web

```bash
cd web
python app.py
```

Mặc định server chỉ nghe ở `http://127.0.0.1:8000` và không cần mật khẩu.

### Mở cho máy khác hoặc internet

Server từ chối khởi động trên địa chỉ không phải loopback nếu chưa đặt mật khẩu.

```bat
set ANTI_DRONE_PASSWORD=mat-khau-cua-ban
web\start.bat
```

`start.bat` chạy server rồi mở tunnel `cloudflared`. Trình duyệt sẽ hỏi đăng nhập: tên bất kỳ, mật khẩu là `ANTI_DRONE_PASSWORD`. `stop.bat` chỉ dừng đúng tiến trình server đã ghi trong `web/server.pid`.

### Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `ANTI_DRONE_PASSWORD` | (trống) | Bật xác thực HTTP Basic cho mọi trang, API và WebSocket |
| `ANTI_DRONE_HOST` / `ANTI_DRONE_PORT` | `127.0.0.1` / `8000` | Địa chỉ nghe |
| `ANTI_DRONE_MAX_VIDEO_TASKS` | `2` | Số video xử lý đồng thời |
| `ANTI_DRONE_VIDEO_TTL_SECONDS` | `3600` | Thời gian giữ video tạm trong `web/tmp/` |
| `ANTI_DRONE_DEVICE` | `auto` | `cpu`, `cuda:0`… |
| `ANTI_DRONE_VIDEO_MIN_CONFIDENCE` | `0.10` | Ngưỡng detector khi phân tích video |
| `ANTI_DRONE_ACTIVE_TRACK_TTL` | `4.0` | Số giây giữ track khi mất dấu |
| `ANTI_DRONE_REID_MEMORY_SECONDS` | `60.0` | Thời gian nhớ để nhận lại ID |
| `ANTI_DRONE_REID_MATCH_THRESHOLD` | `0.45` | Ngưỡng khoảng cách ngoại hình khi nhận lại ID |
| `ANTI_DRONE_NEW_TRACK_MIN_CONFIDENCE` | `0.25` | Confidence tối thiểu để tạo ID mới |
| `ANTI_DRONE_TRACK_CONFIRM_HITS` | `3` | Số khung hình liên tiếp một box phải xuất hiện trước khi được cấp ID và được vẽ |
| `ANTI_DRONE_MOTION_GATE` | `1.5` | Bán kính tìm kiếm quanh vị trí dự đoán của track, tính bằng số đường chéo box |
| `ANTI_DRONE_MOTION_GATE_GROWTH` | `5.0` | Mức nới bán kính trên mỗi giây track bị mất dấu |
| `ANTI_DRONE_CAMERA_INDEX` | `0` | Camera USB của server cho `/ws/camera` |

Giới hạn upload là 500 MB, định dạng `.mp4 .avi .mkv .mov` (`web/backend/config.py`).

## Training và đánh giá

Các script train mặc định dùng đường dẫn trên server training; ghi đè bằng biến môi trường khi chạy ở máy khác.

```bash
# Train ma trận 3 model x 2 kích thước ảnh
FPV_DATA=data/data_train FPV_RUN_ROOT=artifacts/runs python scripts/train_matrix_fresh.py

# Đánh giá trên tập test, chọn model, export ONNX/NCNN/TFLite
python scripts/postprocess_fresh_matrix.py

# So sánh cấu hình tracker trên một video
python scripts/evaluate_tracker_grid.py <video.mp4> web/models/drone-yolov8n-fresh-480.pt

# Lấy mẫu phát hiện của mọi checkpoint trên hai clip kiểm tra
python scripts/evaluate_fresh_models_on_videos.py --models-dir web/models \
  --indoor <indoor.mp4> --outdoor <outdoor.mp4> --output result.json

# Thống kê dataset và artifacts
python scripts/audit_workspace.py
```

## Kiểm thử

```bash
pip install -r web/requirements-test.txt
python -m pytest web/tests/test_tracker_long_term_reid.py web/tests/test_app_api.py -q
```

Hai bộ test này không cần `ultralytics` hay GPU và là bộ chạy trên CI. `web/tests/test_model_engine.py` nạp model thật nên cần cài đầy đủ `web/requirements.txt`.

## Tài liệu

- [Tổng quan tài liệu](docs/README.md)
- [Mô tả repository](docs/description/README.md), [dataset](docs/description/DATASETS.md), [training](docs/description/TRAINING.md)
- [Kế hoạch](docs/plan/README.md) và [báo cáo](docs/report/README.md)

Một số tài liệu trong `docs/` mô tả các script của giai đoạn trước (`train_gpu.py`, `run_phase5.py`…) hiện không còn trong nhánh này.

## Quy tắc cập nhật

1. Không commit dataset, cache, log, video tạm hay checkpoint thử nghiệm; `.gitignore` đã chặn các loại này.
2. Thay đổi hành vi web phải kèm test trong `web/tests/` và chạy được trên CI.
3. Khi thêm biến môi trường hoặc script mới, cập nhật README trong cùng thay đổi.
