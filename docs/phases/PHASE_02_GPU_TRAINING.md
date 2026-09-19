# Phase 02 — GPU training

Trạng thái: `TODO`

## Mục tiêu

Train và lưu checkpoint YOLO trên GPU máy tính, có thể resume, tái lập và truy
ngược được về dataset/config.

## Phạm vi

Train YOLOv8n, YOLO11n và YOLO26n ở 640 làm baseline; chạy multi-seed cho model
ứng viên; chỉ thử 960 nếu size histogram chứng minh cần thiết.

Không train trên Pi, không dùng test set để chọn model và không export trong phase này.

## Điều kiện đầu vào

- Phase 01 đã `DONE`.
- `.runtime/datasets/drone-single-class/audit.json` là `valid`.
- Máy train nhận CUDA.
- Config model và training đã tồn tại.

## Cấu hình mặc định

```yaml
dataset: drone-single-class
models: [yolov8n, yolov11n, yolo26n]
imgsz: 640
seed: 42
device: 0
amp: true
early_stopping: true
```

Batch size và workers phải được resolve theo VRAM/CPU thật, không hard-code theo
máy tham khảo.

## Lệnh thực hiện

```bash
cd /run/media/pnt/APP/anti_drone

anti-drone train --dataset drone-single-class --model yolov8n \
  --imgsz 640 --seed 42 --device 0 --dry-run

anti-drone train --dataset drone-single-class --model yolov8n \
  --imgsz 640 --seed 42 --device 0 \
  --run-name baseline-s42

anti-drone train --dataset drone-single-class --model yolov11n \
  --imgsz 640 --seed 42 --device 0 \
  --run-name baseline-s42

anti-drone train --dataset drone-single-class --model yolo26n \
  --imgsz 640 --seed 42 --device 0 \
  --run-name baseline-s42
```

Sau khi có model ứng viên:

```bash
anti-drone train --dataset drone-single-class --model <candidate> \
  --imgsz 640 --seed 123 --device 0 --run-name baseline-s123

anti-drone train --dataset drone-single-class --model <candidate> \
  --imgsz 640 --seed 3407 --device 0 --run-name baseline-s3407
```

Resume:

```bash
anti-drone resume --checkpoint \
  artifacts/experiments/drone-single-class/<model-id>/<run-name>/weights/last.pt
```

## Output bắt buộc

```text
artifacts/experiments/drone-single-class/<model-id>/<run-name>/
├── args.yaml
├── provenance.json
├── results.csv
├── plots/
└── weights/
    ├── best.pt
    └── last.pt
```

## Checklist

- [ ] Dry-run resolve đúng dataset, config và CUDA.
- [ ] Log xác nhận `device=0` là GPU.
- [ ] Không ghi đè run cũ.
- [ ] Có `best.pt` và `last.pt`.
- [ ] Có `results.csv` và plots.
- [ ] Có provenance package/Git/config/dataset.
- [ ] Seed được ghi trong args.
- [ ] Test split không được dùng trong train hoặc model selection.

## Acceptance gate

Mỗi run phải có checkpoint, results và provenance. Training phải thực sự dùng
GPU CUDA. Không chuyển Phase 03 nếu dataset manifest hoặc run metadata thiếu.

## Dừng hoặc quay lại

- Dừng nếu CUDA không được nhận.
- Giảm batch hoặc workers nếu OOM.
- Quay lại Phase 01 nếu phát hiện lỗi label trong training log.
- Dừng run nếu output bị ghi đè hoặc provenance không sinh được.

## Provenance

Lưu model config, dataset manifest hash, training args, seed, device, batch,
workers, package versions, GPU name, start/end time, Git state và checkpoint hash.

