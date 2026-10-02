# Phase 06 — Benchmark and release

Trạng thái: `BLOCKED_PI_HARDWARE`

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

python scripts/benchmark_phase6.py --runtime onnx \
  --model artifacts/deploy/yolov8n/onnx/best.onnx \
  --input .runtime/parity-set --warmup 200 --frames 1000 \
  --output-root artifacts/benchmarks/pi5-cpu

python scripts/benchmark_phase6.py --runtime ncnn \
  --model artifacts/deploy/yolov8n/ncnn/best_ncnn_model \
  --input .runtime/parity-set --warmup 200 --frames 1000 \
  --output-root artifacts/benchmarks/pi5-cpu

python scripts/benchmark_phase6.py --runtime tflite \
  --model artifacts/deploy/yolov8n/tflite/model_float32.tflite \
  --input .runtime/parity-set --warmup 200 --frames 1000 \
  --output-root artifacts/benchmarks/pi5-cpu

PYTHONPATH=src python scripts/run_phase5.py camera --device /dev/video0 \
  --runtime <runtime> --duration-seconds 1800 \
  --model <runtime-model> --output artifacts/benchmarks/pi5-cpu/<runtime>/<run-id>
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

Release candidate hiện bị `BLOCKED_PI_VALIDATION`: ba benchmark đã có host
reference nhưng chưa có Pi 5, camera và sustained 30 phút. Không dùng số host
thay cho benchmark thực tế trên Pi.

## Dừng hoặc quay lại

- Quay lại Phase 05 nếu camera pipeline không ổn định.
- Quay lại Phase 04 nếu parity sai.
- Quay lại Phase 03 nếu runtime cần threshold khác với threshold đã khóa.
- Dừng release nếu benchmark chưa đủ environment metadata.

## Provenance

Lưu Pi hardware, OS/kernel, camera, runtime versions, model/checksum, config,
CPU governor, warm-up, frame count, duration, command và timestamp.
