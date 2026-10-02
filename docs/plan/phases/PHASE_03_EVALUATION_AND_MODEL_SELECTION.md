# Phase 03 — Evaluation and model selection

Trạng thái: `TODO`

## Mục tiêu

Đánh giá checkpoint theo một protocol cố định, chọn model release candidate và
khóa threshold trước khi export.

## Phạm vi

Bao gồm validation, test sau khi khóa candidate, size-bin metrics, hard-negative,
negative video, threshold sweep và multi-seed analysis.

Không chỉnh model hoặc threshold theo kết quả test cuối.

## Điều kiện đầu vào

- Phase 02 đã `DONE`.
- Có các checkpoint `best.pt` hợp lệ.
- Dataset manifest và split registry không đổi.
- Evaluation config đã được ghi version.

## Protocol

- IoU matching: `0.50`.
- Confidence sweep trên validation/development set.
- NMS IoU phải ghi rõ trong report.
- Size bins: `<4`, `4–8`, `8–16`, `16–32`, `32–64`, `>64` pixel.
- Negative video không có drone phải được đánh giá riêng.
- Test set chỉ mở sau khi model và threshold đã khóa.

## Lệnh thực hiện

```bash
cd /run/media/pnt/APP/anti_drone

anti-drone evaluate --dataset drone-single-class \
  --checkpoint artifacts/experiments/drone-single-class/<model-id>/<run-name>/weights/best.pt \
  --split val --output-root artifacts/benchmarks/model-selection/<model-id>

anti-drone threshold-sweep --dataset drone-single-class \
  --checkpoint <checkpoint> \
  --split val --conf-start 0.05 --conf-end 0.60 --conf-step 0.05 \
  --nms-iou 0.70 \
  --output artifacts/benchmarks/model-selection/<model-id>/threshold_sweep.csv

anti-drone evaluate-negative-video \
  --checkpoint <checkpoint> \
  --input <negative-video-root> \
  --output artifacts/benchmarks/model-selection/<model-id>/negative_video_metrics.csv

anti-drone evaluate --dataset drone-single-class \
  --checkpoint <locked-checkpoint> \
  --split test --locked-threshold <locked-threshold> \
  --output-root artifacts/benchmarks/model-selection/<model-id>
```

## Tiêu chí chọn model

Model winner phải cân bằng:

1. Recall drone nhỏ.
2. Precision và F1.
3. False alarm/hour.
4. Độ ổn định giữa seed.
5. Khả năng export sang ba runtime.
6. Kết quả benchmark CPU dự kiến.

Không chọn winner chỉ theo mAP50-95.

## Output bắt buộc

```text
artifacts/benchmarks/model-selection/<model-id>/
├── metrics.json
├── metrics.csv
├── threshold_sweep.csv
├── negative_video_metrics.csv
├── size_bin_metrics.csv
├── provenance.json
└── MODEL_SELECTION.md
```

## Checklist

- [ ] Validation metrics đầy đủ.
- [ ] Size-bin metrics đầy đủ.
- [ ] Negative-video metrics có false alarm/hour.
- [ ] Threshold được chọn trên validation.
- [ ] Test chỉ chạy sau khi khóa candidate.
- [ ] Multi-seed variance được báo cáo.
- [ ] Các model bị loại có lý do.
- [ ] Model ID và threshold được ghi vào `MODEL_SELECTION.md`.

## Acceptance gate

Phải có đúng một model release candidate, threshold đã khóa, test protocol đã
đóng băng và report giải thích được quyết định chọn model.

## Dừng hoặc quay lại

- Quay lại Phase 02 nếu checkpoint lỗi hoặc kết quả không tái lập.
- Quay lại Phase 01 nếu phát hiện leakage hoặc label sai.
- Dừng nếu test bị chạy trước khi threshold khóa; tạo run mới thay vì ghi đè.

## Provenance

Lưu checkpoint hash, dataset manifest hash, evaluation config, threshold grid,
NMS IoU, matching IoU, software versions, command và thời gian chạy.

