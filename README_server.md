# anti_drone

Dự án phát hiện drone từ camera USB, train trên máy có GPU CUDA và chạy suy luận CPU trên Raspberry Pi 5 4GB. Mục tiêu là một pipeline anti-drone có thể kiểm thử, benchmark và tái triển khai được; dự án không điều khiển cơ cấu chấp hành, không dẫn đường và không có chức năng vũ khí.

## Dự án làm gì?

Pipeline nhận frame từ camera USB, chạy detector một class `0 = drone`, lọc NMS, theo dõi đối tượng qua nhiều frame bằng ByteTrackLite và phát alert khi trạng thái đủ ổn định. Pi chỉ làm capture, preprocessing, inference, tracking, overlay và ghi log. Toàn bộ dataset preparation, training, evaluation và export model được thực hiện trên máy GPU; không train hoặc export trên Pi.

Các runtime deploy được hỗ trợ:

- ONNX Runtime.
- NCNN.
- TFLite/LiteRT.

Phiên bản v1 không dùng Hailo, AI HAT, TensorRT hoặc accelerator riêng.

## Kiến trúc

```text
USB camera
    -> latest-frame capture queue
    -> letterbox 640x640
    -> detector runtime (ONNX / NCNN / TFLite)
    -> NMS
    -> ByteTrackLite
    -> multi-frame alert state
    -> overlay + terminal log
```

Model được chọn là `yolov8n` vì đạt trade-off tốt nhất giữa validation quality và khả năng chạy CPU trên Pi 5. Checkpoint train nằm tại `artifacts/experiments/drone-single-class/yolov8n/`.

## Dataset policy

Dataset gốc được giữ trong `data/import_data_rar/`; các archive tải chưa xong không được đưa vào training. Dataset đã xử lý phải có:

- Ba split không trùng ảnh: `train`, `val`, `test`.
- Tỷ lệ mục tiêu `70% / 20% / 10%`.
- `my_dataset` bắt buộc nằm trong `train`.
- Split theo video/sequence để tránh leakage giữa các split.
- Class duy nhất: `0 = drone`.
- Manifest, checksum, label statistics và audit report.

Dataset runtime sau audit nằm tại `data/processed/drone-single-class/` và manifest được kiểm tra bất biến trước khi release model.

## Kết quả Pi 5 đã đo

Đo trên Raspberry Pi 5 4GB, CPU, input 640, sau 200 frame warm-up và 1000 frame benchmark:

| Runtime | Model-only | End-to-end | End-to-end p95 | RAM peak | Nhiệt độ tối đa |
|---|---:|---:|---:|---:|---:|
| ONNX Runtime | 7.10 FPS | 6.77 FPS | 154.81 ms | xem report | 53.45°C |
| NCNN | 14.20 FPS | 12.85 FPS | 81.13 ms | 211.6 MB | 47.40°C |
| TFLite/LiteRT | 7.76 FPS | 7.35 FPS | 138.79 ms | 296.2 MB | 52.35°C |

NCNN là profile nhanh nhất trong phép đo hiện tại. Mỗi runtime cũng đã chạy camera live đủ 1800 giây không có capture error.

Chi tiết evidence:

- [Pi execution status](docs/PI5_EXECUTION_STATUS.md)
- [Release candidate](artifacts/releases/yolov8n/RELEASE_CANDIDATE.md)
- [Independent verification](artifacts/releases/yolov8n/VERIFICATION.json)
- [Pi benchmark artifacts](artifacts/benchmarks/pi5-cpu/)

## Chạy trên Pi

Bundle release: `artifacts/releases/yolov8n/anti-drone-yolov8n-pi5.tar.gz`.

Camera live sau khi cài bundle:

```bash
cd /path/to/anti-drone
. .venv-pi/bin/activate
PYTHONPATH=src python scripts/run_phase5.py camera \
  --runtime ncnn \
  --model artifacts/deploy/yolov8n/ncnn/best_ncnn_model \
  --device /dev/video0 \
  --imgsz 640 \
  --output .runtime/pi-camera/ncnn
```

Xem log live:

```bash
tail -f .runtime/pi-camera/ncnn/runtime.log
```

## Xem màn hình vật lý bằng Remmina

Pi hiện dùng RealVNC service mode. Trong Remmina chọn:

```text
Protocol: VNC
Server: 192.168.1.118:5900
Username: để trống
```

Port `3389` là XRDP session riêng, không phải màn hình vật lý.

## Train và đánh giá trên GPU

Các lệnh train chỉ chạy trên máy GPU:

```bash
conda env create -f environment.yml
conda activate anti-drone
pip install -r requirements-dev.txt
python scripts/train_gpu.py --dataset drone-single-class --model yolov8n
```

Các phase training, evaluation và model selection đều ghi provenance, seed, Git state, package versions, checkpoint `best.pt`/`last.pt` và validation metrics. Test split chỉ được mở sau khi khóa candidate và threshold.

## Runbook theo phase

Đọc [docs/phases/README.md](docs/phases/README.md) rồi thực hiện tuần tự:

1. [Repository baseline](docs/phases/PHASE_00_REPOSITORY_BASELINE.md)
2. [Dataset ingestion and audit](docs/phases/PHASE_01_DATASET_INGESTION_AND_AUDIT.md)
3. [GPU training](docs/phases/PHASE_02_GPU_TRAINING.md)
4. [Evaluation and model selection](docs/phases/PHASE_03_EVALUATION_AND_MODEL_SELECTION.md)
5. [Export and runtime parity](docs/phases/PHASE_04_EXPORT_AND_RUNTIME_PARITY.md)
6. [Pi 5 camera pipeline](docs/phases/PHASE_05_PI5_USB_CAMERA_PIPELINE.md)
7. [Benchmark and release](docs/phases/PHASE_06_BENCHMARK_AND_RELEASE.md)
8. [Retraining and maintenance](docs/phases/PHASE_07_RETRAINING_AND_MAINTENANCE.md)

Tài liệu giải thích tổng quan:

- [Datasets](docs/DATASETS.md)
- [Training](docs/TRAINING.md)
- [Repository layout](docs/REPOSITORY_LAYOUT.md)
- [Research plan](docs/RESEARCH_PLAN.md)
- [Pi handoff](docs/PI5_HANDOFF.md)

## Cấu trúc repository

```text
anti_drone/
├── configs/                 # dataset và model config
├── data/                    # dataset local; không commit archive lớn
├── artifacts/               # checkpoint, export, benchmark, release evidence
├── .runtime/                # manifest và kết quả chạy local/Pi
├── docs/                    # tài liệu tổng quan và phase runbook
├── scripts/                 # prepare, train, evaluate, export, benchmark
├── src/anti_drone/          # runtime detector/tracker/alert pipeline
├── tests/                   # runtime tests và contract tests
├── requirements.txt         # dependency máy GPU/host
├── requirements-pi.txt      # dependency inference trên Pi
└── README.md
```

Dataset, checkpoint và benchmark là local artifacts; `.gitignore` ngăn chúng được commit nhầm. Không xóa dataset gốc hoặc evidence release nếu chưa có bản sao lưu và chưa tạo version dataset thay thế.
