# Phase 04 — Export and runtime parity

Trạng thái: `TODO`

## Mục tiêu

Đóng gói model release candidate thành ba profile CPU: ONNX Runtime, NCNN và
TensorFlow Lite; kiểm tra output tương đương với PyTorch.

## Phạm vi

Bao gồm export, load test, preprocessing contract, postprocessing contract,
metadata và checksum.

Không benchmark camera live hoặc sửa threshold trong phase này.

## Điều kiện đầu vào

- Phase 03 đã `DONE`.
- Có checkpoint và threshold đã khóa.
- Input size đã khóa.
- Có representative parity set đã cố định.

## Contract preprocessing

- Input size cố định, mặc định `640x640`.
- Letterbox giữ aspect ratio.
- Padding phải được ghi trong metadata.
- RGB/BGR phải thống nhất giữa ba runtime.
- Normalization phải được ghi rõ.
- Output raw/NMS phải được xác định rõ.

## Lệnh thực hiện

```bash
cd /run/media/pnt/APP/anti_drone

anti-drone export --checkpoint <locked-checkpoint> \
  --runtime onnx --imgsz 640 \
  --output artifacts/deploy/<model-id>/onnx

anti-drone export --checkpoint <locked-checkpoint> \
  --runtime ncnn --imgsz 640 \
  --output artifacts/deploy/<model-id>/ncnn

anti-drone export --checkpoint <locked-checkpoint> \
  --runtime tflite --imgsz 640 \
  --output artifacts/deploy/<model-id>/tflite

anti-drone parity --checkpoint <locked-checkpoint> \
  --profiles artifacts/deploy/<model-id> \
  --input .runtime/parity-set \
  --output artifacts/deploy/<model-id>/parity.json

sha256sum artifacts/deploy/<model-id>/**/* \
  > artifacts/deploy/<model-id>/SHA256SUMS
```

## Output bắt buộc

```text
artifacts/deploy/<model-id>/
├── metadata.json
├── parity.json
├── SHA256SUMS
├── onnx/
├── ncnn/
└── tflite/
```

## Checklist

- [ ] Ba runtime có model file.
- [ ] Ba runtime load được trên CPU.
- [ ] Input contract giống nhau.
- [ ] Class map giống nhau.
- [ ] RGB/BGR được xác nhận bằng test.
- [ ] Normalization không bị nhân/chia hai lần.
- [ ] Box restore sau letterbox đúng.
- [ ] Confidence và NMS dùng threshold đã khóa.
- [ ] Parity report có tolerance và số frame.
- [ ] Có checksum.

## Acceptance gate

Cả ba profile phải inference được cùng bộ input và output nằm trong tolerance đã
định nghĩa. Profile không đạt phải ghi `BLOCKED` và không được đưa sang Phase 05.

## Dừng hoặc quay lại

- Quay lại exporter nếu model không load.
- Quay lại Phase 03 nếu chỉ có thể đạt parity bằng cách đổi threshold.
- Quay lại preprocess nếu box lệch do RGB/BGR hoặc letterbox.
- Không sửa thủ công model binary sau khi checksum đã sinh.

## Provenance

Lưu checkpoint hash, exporter version, runtime library version, input contract,
converter command, parity set hash, tolerance, output hash và timestamp.

