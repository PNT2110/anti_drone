# Phase 04 — Export and runtime parity

Trạng thái: `DONE`

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

python scripts/export_phase4.py --model-id yolov8n --imgsz 640

python scripts/export_phase4.py --model-id yolov8n --imgsz 640
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

Cả ba profile đã inference được cùng bộ input; parity được ghi trong
`artifacts/deploy/yolov8n/parity.json` với tolerance confidence 0.05 và box 5 px.

## Dừng hoặc quay lại

- Quay lại exporter nếu model không load.
- Quay lại Phase 03 nếu chỉ có thể đạt parity bằng cách đổi threshold.
- Quay lại preprocess nếu box lệch do RGB/BGR hoặc letterbox.
- Không sửa thủ công model binary sau khi checksum đã sinh.

## Provenance

Lưu checkpoint hash, exporter version, runtime library version, input contract,
converter command, parity set hash, tolerance, output hash và timestamp.
