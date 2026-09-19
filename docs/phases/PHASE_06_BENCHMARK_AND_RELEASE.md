# Phase 06 — Benchmark and release

Trạng thái: `TODO`

## Mục tiêu

Đo công bằng ba runtime trên Pi 5 4GB và tạo release candidate có benchmark,
checksum, giới hạn và hướng dẫn chạy rõ ràng.

## Phạm vi

Bao gồm model-only latency, end-to-end camera latency, FPS, dropped frames,
RAM, CPU, nhiệt độ, accuracy parity và sustained run.

## Điều kiện đầu vào

- Phase 05 đã `DONE`.
- Camera pipeline chạy được.
- Có replay set cố định.
- Có model checksum và runtime metadata.

## Protocol cố định

Mỗi runtime phải dùng:

- Cùng model ID.
- Cùng input size.
- Cùng replay set.
- Cùng threshold/NMS.
- Warm-up trước đo.
- Ít nhất 1.000 frame replay.
- Ít nhất 30 phút camera continuous run.

Không benchmark khi có process train hoặc process nặng khác trên Pi.

## Lệnh thực hiện

```bash
cd /path/to/anti_drone

anti-drone benchmark --runtime onnx \
  --model artifacts/deploy/<model-id>/onnx \
  --input .runtime/replay-set \
  --warmup 200 --frames 1000 --output artifacts/benchmarks/pi5-cpu/onnx/<run-id>

anti-drone benchmark --runtime ncnn \
  --model artifacts/deploy/<model-id>/ncnn \
  --input .runtime/replay-set \
  --warmup 200 --frames 1000 --output artifacts/benchmarks/pi5-cpu/ncnn/<run-id>

anti-drone benchmark --runtime tflite \
  --model artifacts/deploy/<model-id>/tflite \
  --input .runtime/replay-set \
  --warmup 200 --frames 1000 --output artifacts/benchmarks/pi5-cpu/tflite/<run-id>

anti-drone camera-benchmark --device /dev/video0 \
  --runtime <runtime> --duration-seconds 1800 \
  --output artifacts/benchmarks/pi5-cpu/<runtime>/<run-id>
```

## Output bắt buộc

```text
artifacts/benchmarks/pi5-cpu/<runtime>/<run-id>/
├── benchmark.json
├── per_frame.csv
├── environment.json
├── thermal.log
├── runtime.log
└── summary.md
```

## Metrics

- Model-only latency: mean, p50, p95, p99.
- End-to-end latency: mean, p50, p95, p99.
- FPS thực tế.
- Dropped frames.
- CPU utilization.
- RSS memory.
- Nhiệt độ.
- Throttle state.
- Detection parity.
- False alert count.

## Checklist

- [ ] Ba runtime có benchmark riêng.
- [ ] Model-only và end-to-end được tách riêng.
- [ ] Warm-up và frame count được ghi.
- [ ] Environment Pi được ghi.
- [ ] RAM/CPU/nhiệt độ được ghi.
- [ ] Sustained run không crash.
- [ ] Không có memory leak rõ rệt.
- [ ] Output parity được kiểm tra.
- [ ] Checksum khớp.
- [ ] README cập nhật bằng số thật.
- [ ] Release note ghi giới hạn và runtime được kiểm tra.

## Acceptance gate

Release candidate chỉ được tạo khi ba runtime có kết quả đo hợp lệ, pipeline
không crash trong sustained run và report ghi đủ điều kiện đo. Không dùng số đo
của máy khác hoặc số lý thuyết thay cho benchmark thực tế.

## Dừng hoặc quay lại

- Quay lại Phase 05 nếu camera pipeline không ổn định.
- Quay lại Phase 04 nếu parity sai.
- Quay lại Phase 03 nếu runtime cần threshold khác với threshold đã khóa.
- Dừng release nếu benchmark chưa đủ environment metadata.

## Provenance

Lưu Pi hardware, OS/kernel, camera, runtime versions, model/checksum, config,
CPU governor, warm-up, frame count, duration, command và timestamp.
