# Phase 05 — Raspberry Pi 5 USB camera pipeline

Trạng thái: `TODO`

## Mục tiêu

Chạy inference, tracking và cảnh báo trên Raspberry Pi 5 RAM 4GB với USB camera,
không train và không export model trên Pi.

## Phạm vi

Bao gồm cài runtime, image replay, camera capture, preprocessing, inference,
NMS, ByteTrack, overlay, terminal log, frame drop và camera reconnect.

Không bao gồm GPIO, buzzer hoặc điều khiển thiết bị ngoài.

## Điều kiện đầu vào

- Phase 04 đã `DONE` cho profile runtime cần thử.
- Pi chạy OS 64-bit.
- Pi có RAM 4GB.
- USB camera được kết nối.
- Có model artifact và `metadata.json`.

## Kiểm tra phần cứng

```bash
uname -a
getconf LONG_BIT
free -h
lsusb
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
```

## Cài runtime

```bash
python3 -m venv .venv-pi
source .venv-pi/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-pi.txt
```

Chỉ cài runtime profile đang kiểm tra khi cần; ghi version package vào report.

## Image replay trước camera

```bash
anti-drone replay --runtime onnx \
  --model artifacts/deploy/<model-id>/onnx \
  --input .runtime/replay-set \
  --output .runtime/pi-replay/onnx

anti-drone replay --runtime ncnn \
  --model artifacts/deploy/<model-id>/ncnn \
  --input .runtime/replay-set \
  --output .runtime/pi-replay/ncnn

anti-drone replay --runtime tflite \
  --model artifacts/deploy/<model-id>/tflite \
  --input .runtime/replay-set \
  --output .runtime/pi-replay/tflite
```

## Chạy camera

```bash
anti-drone camera \
  --device /dev/video0 \
  --runtime onnx \
  --model artifacts/deploy/<model-id>/onnx \
  --camera-width 1280 --camera-height 720 --camera-fps 30 \
  --show-overlay --log-events
```

Runtime đổi bằng `--runtime onnx`, `--runtime ncnn` hoặc `--runtime tflite`.

## Pipeline bắt buộc

```text
capture -> latest-frame queue -> letterbox -> inference -> NMS
        -> ByteTrack -> alert state -> overlay + terminal log
```

Queue chỉ giữ frame mới nhất. Khi inference chậm, frame cũ bị bỏ để tránh tăng
latency.

## Alert state machine

Giá trị mặc định, có thể đổi trong config:

- Tạo track mới sau 3 detection trong 5 frame.
- Giữ track tối đa 15 frame khi mất detection.
- Không cảnh báo từ một detection đơn lẻ.
- Có cooldown giữa hai alert liên tiếp.
- Log `frame_id`, `track_id`, bbox, confidence và latency.

## Checklist

- [ ] Pi nhận đúng 64-bit OS.
- [ ] Pi có đủ RAM cho runtime.
- [ ] `/dev/video0` mở được.
- [ ] Replay chạy trước camera live.
- [ ] Ba runtime có thể đổi bằng CLI.
- [ ] Overlay hiển thị bbox/track/FPS.
- [ ] Frame queue không tăng vô hạn.
- [ ] Camera disconnect được xử lý.
- [ ] Track không tạo ID mới bất thường.
- [ ] Alert cần nhiều frame xác nhận.
- [ ] Không có lệnh train/export trên Pi.

## Acceptance gate

Camera chạy liên tục, inference thành công, tracking ổn định và alert state
machine hoạt động đúng trên test sequence. Runtime lỗi phải được ghi rõ là
`BLOCKED`, không được đánh dấu `DONE` bằng replay một frame.

## Dừng hoặc quay lại

- Quay lại Phase 04 nếu parity hoặc model load lỗi.
- Dừng nếu camera không cung cấp frame ổn định.
- Quay lại preprocess nếu bbox sai vị trí.
- Quay lại tracker/alert test nếu cảnh báo từ một frame.

## Provenance

Lưu Pi model/RAM/OS/kernel, camera model, resolution/FPS, runtime version,
model checksum, config checksum, thermal snapshot và command chạy.

