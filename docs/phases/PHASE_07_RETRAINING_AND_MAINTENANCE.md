# Phase 07 — Retraining and maintenance

Trạng thái: `BASELINE_FROZEN_NO_NEW_BATCH`

## Mục tiêu

Thêm dữ liệu hoặc model mới mà không phá vỡ dataset v1, baseline model và
release đang chạy trên Pi.

## Phạm vi

Bao gồm batch dữ liệu mới, review label, version dataset, retrain/incremental
train, so sánh baseline, re-export và benchmark lại.

Không sửa trực tiếp dataset v1 hoặc thay release chỉ vì một metric tăng nhỏ.

## Điều kiện đầu vào

- Có baseline release đã qua Phase 06.
- Dữ liệu mới được đặt trong batch riêng.
- Có source metadata và quyền sử dụng dữ liệu.
- Có người review annotation.

## Quy trình

```bash
cd /run/media/pnt/APP/anti_drone

mkdir -p data/incoming/batch_<YYYYMMDD>

anti-drone dataset inventory --input data/incoming/batch_<YYYYMMDD>
anti-drone dataset review --input data/incoming/batch_<YYYYMMDD>
anti-drone dataset prepare --version v2 \
  --base-manifest .runtime/datasets/drone-single-class/manifest.json \
  --input data/incoming/batch_<YYYYMMDD>
anti-drone dataset audit --version v2

anti-drone train --dataset drone-single-class-v2 \
  --model <baseline-model> --imgsz 640 --seed 42 --device 0 \
  --run-name retrain-v2-s42

anti-drone compare --baseline <baseline-checkpoint> \
  --candidate <candidate-checkpoint> \
  --dataset drone-single-class-v2
```

Chỉ sau khi candidate thắng hoặc có trade-off được chấp thuận mới chạy lại
Phase 04, Phase 05 và Phase 06.

## Quy tắc dữ liệu mới

- Không trộn batch mới trực tiếp vào `data/`.
- Không dùng pseudo-label chưa review.
- Không di chuyển video cũ khỏi split registry.
- Kiểm tra duplicate với dataset v1.
- Giữ test set cũ để so sánh regression.
- Tạo test bổ sung riêng cho domain mới.

## Output bắt buộc

```text
.runtime/datasets/drone-single-class-v2/
├── data.yaml
├── audit.json
├── manifest.json
├── split_registry.json
└── label_statistics.json

artifacts/experiments/drone-single-class-v2/<model-id>/<run-name>/
artifacts/benchmarks/model-selection-v2/
```

## Checklist

- [ ] Dataset v1 vẫn nguyên vẹn.
- [ ] Batch mới có checksum.
- [ ] Label mới đã review.
- [ ] Split registry không leakage.
- [ ] Duplicate đã kiểm tra.
- [ ] Baseline và candidate được đánh giá cùng protocol.
- [ ] Regression trên test cũ được báo cáo.
- [ ] Candidate qua Phase 03.
- [ ] Ba runtime được export lại.
- [ ] Pi benchmark được chạy lại.
- [ ] Changelog và provenance được cập nhật.

## Acceptance gate

Version mới chỉ được release khi không phá baseline ngoài ngưỡng đã định nghĩa,
đã qua evaluation, parity, Pi pipeline và benchmark. Nếu không đạt, giữ release
cũ và đánh dấu candidate `BLOCKED`.

## Dừng hoặc quay lại

- Quay lại Phase 01 nếu audit batch mới không hợp lệ.
- Quay lại Phase 02 nếu train candidate lỗi.
- Quay lại Phase 03 nếu candidate không thắng baseline.
- Quay lại Phase 04–06 nếu export hoặc runtime regression.

## Provenance

Lưu parent dataset/version, batch checksum, label reviewer, split registry hash,
baseline checkpoint hash, candidate hash, evaluation report, export hash và
benchmark report.

## Trạng thái thực thi hiện tại

Dataset v1 được giữ nguyên, chưa có batch dữ liệu mới đã review nên chưa tạo
dataset v2 hoặc chạy retrain giả. Audit baseline được ghi tại
`artifacts/maintenance/yolov8n/phase7_status.json`; khi có batch mới phải quay
lại Phase 01 rồi mới đi tiếp Phase 02–06.
