---
license: other
license_name: mixed-see-dataset-sources
language:
  - vi
  - en
library_name: ultralytics
pipeline_tag: object-detection
tags:
  - yolo
  - drone-detection
  - anti-uav
  - object-tracking
  - fpv
---

# anti_drone — phát hiện và tracking drone (YOLO)

Toàn bộ dự án `anti_drone`: mã nguồn, mô hình đã huấn luyện, dữ liệu huấn luyện và các bộ dữ liệu nguồn.
Hệ thống phát hiện drone một lớp bằng YOLO, gán ID theo dõi cho từng drone, kèm bảng điều khiển web (FastAPI)
để phân tích video và camera.

Phạm vi: chỉ nhận diện, tracking và cảnh báo phần mềm. Dự án không điều khiển cơ cấu chấp hành hay vũ khí.

Mã nguồn cũng có trên GitHub: https://github.com/PNT2110/anti_drone

## Nội dung repository

| Đường dẫn | Nội dung |
|---|---|
| `web/` | Bảng điều khiển web: `app.py` (REST, MJPEG, WebSocket), `backend/` (detector, tracker, quản lý model), giao diện, test |
| `web/models/` | 6 checkpoint PyTorch dùng cho web, cùng bản ONNX/TFLite của model được chọn |
| `models/` | Các bản export ONNX/NCNN cho Raspberry Pi |
| `scripts/` | Train ma trận model, hậu xử lý, đánh giá tracker, công cụ tải lên |
| `configs/` | Cấu hình dataset, model, tracker, training |
| `artifacts/` | Bundle triển khai, kết quả train (`results.csv`, `args.yaml`), video và khung hình kiểm thử |
| `docs/` | Mô tả, kế hoạch và báo cáo |
| `dataset_archives/data_train/` | Bộ dữ liệu huấn luyện đã gộp, đóng gói theo tập |
| `dataset_archives/import_data_rar/` | Các file nén dữ liệu nguồn |

## Mô hình

Sáu mô hình một lớp (`drone`), huấn luyện 30 epoch từ trọng số pretrain, batch 8, ở hai kích thước ảnh.
Chỉ số dưới đây đo trên tập test của `data_train`:

| Mô hình | Ảnh | mAP50 | mAP50-95 | Precision | Recall |
|---|---|---|---|---|---|
| YOLOv8n | 480 | 0,927 | 0,601 | 0,932 | 0,890 |
| YOLOv8n | 640 | 0,930 | 0,608 | 0,934 | 0,893 |
| YOLO11n | 480 | 0,926 | 0,605 | 0,932 | 0,892 |
| YOLO11n | 640 | 0,934 | 0,612 | 0,938 | 0,901 |
| YOLO26n | 480 | 0,930 | 0,606 | 0,935 | 0,892 |
| YOLO26n | 640 | 0,933 | 0,615 | 0,937 | 0,901 |

YOLO26n-640 có mAP50-95 cao nhất trên tập validation (0,709) và là bản được export sang ONNX/NCNN/TFLite.
Web mặc định dùng `drone-yolov8n-fresh-480.pt`.

```python
from ultralytics import YOLO

model = YOLO("web/models/drone-yolov8n-fresh-480.pt")
results = model.predict("frame.jpg", imgsz=960, conf=0.25)
```

## Dữ liệu

### `dataset_archives/data_train/`

Bộ huấn luyện định dạng YOLO, một lớp `drone`. Mỗi tập là một file `.tar` chứa cả `images/<tập>/` và `labels/<tập>/`.

| File | Số ảnh | Dung lượng |
|---|---|---|
| `train.tar` | 63.028 | 11,6 GB |
| `val.tar` | 25.781 | 3,9 GB |
| `test.tar` | 21.660 | 1,9 GB |

Kèm theo: `data.yaml`, `manifest.json` (danh sách từng ảnh và nguồn gốc), `import_archives_manifest.json`,
`license_ledger.json`.

Giải nén cả ba file vào cùng một thư mục, đặt `data.yaml` vào đó rồi train:

```bash
mkdir data_train && cd data_train
for f in train val test; do tar xf ../dataset_archives/data_train/$f.tar; done
cp ../dataset_archives/data_train/data.yaml .
```

### `dataset_archives/import_data_rar/`

Các file nén nguồn, giữ nguyên như lúc nhập: `Anti-UAV300.tar`, `DUT-Anti-UAV.tar`, `UAV-CB.tar`,
`Halmstad-Drone.tar`, `Drone-vs-Bird.tar`, `my_dataset.tar.xz`, `extracted_20260930.tar.gz`,
`legacy_local_20260930.tar.gz`.

## Giấy phép và nguồn dữ liệu

Repository gộp nhiều nguồn, mỗi nguồn giữ giấy phép riêng. Theo `license_ledger.json`, bộ `data_train` gồm:

| Nguồn | Giấy phép |
|---|---|
| YOLOv5 Drone Detection Using Multimodal Data Registered by the Vicon System ([Zenodo 14878618](https://zenodo.org/records/14878618)) | CC BY-NC 4.0 — phải ghi nguồn, không dùng thương mại |
| Seraphim Drone Detection Dataset ([lgrzybowski/seraphim-drone-detection-dataset](https://huggingface.co/datasets/lgrzybowski/seraphim-drone-detection-dataset)) | CC BY 4.0 — phải ghi nguồn |
| Dữ liệu và video trong nhà do tác giả tự thu | Do tác giả cung cấp; nhãn giả của video trong nhà chưa được rà soát thủ công |

Vì có thành phần CC BY-NC 4.0, bộ `data_train` và các mô hình huấn luyện từ nó nên được coi là **không dùng cho mục đích thương mại**.

Các file nén trong `import_data_rar/` (Anti-UAV300, DUT-Anti-UAV, UAV-CB, Halmstad-Drone, Drone-vs-Bird) là bộ dữ liệu
của bên thứ ba, được phân phối lại ở đây kèm dự án. Chúng thuộc về tác giả gốc và chịu điều khoản của tác giả gốc;
hãy kiểm tra và trích dẫn nguồn gốc trước khi sử dụng. Nếu bạn là chủ sở hữu và muốn gỡ dữ liệu, hãy mở một thảo luận
trong tab Community.

## Chạy bảng điều khiển web

```bash
pip install -r web/requirements.txt
cd web
python app.py
```

Mở `http://127.0.0.1:8000`. Các biến môi trường `ANTI_DRONE_*` (thiết bị, ngưỡng, tham số tracker) được mô tả trong
`README.md` của mã nguồn trên GitHub.

## Hạn chế đã biết

- Tracker phân biệt các drone bằng chuyển động và một đặc trưng màu đơn giản. Khi một drone mất dấu lâu hoặc đổi
  góc nhìn mạnh, nó có thể được cấp ID mới.
- Với vật thể rất nhỏ, detector có thể hụt drone ở một số khung hình; chạy ở `imgsz=960` cho kết quả tốt hơn 480/640.
- Kết quả đánh giá tracker mới dựa trên hai video kiểm thử, chưa có nhãn ID chuẩn.
