# Pi 5 handoff — anti_drone

The host-side phases are prepared at `artifacts/deploy/yolov8n/`. The current
host is `x86_64` and has no `/dev/video0`, so the final Pi gate must be run on
the Raspberry Pi 5 with the USB camera attached.

## Install and inspect

```bash
uname -m
free -h
python3 -m venv .venv-pi
source .venv-pi/bin/activate
python -m pip install -r requirements-pi.txt
ls -l /dev/video0
```

Copy the repository and `artifacts/deploy/yolov8n/` to the Pi without changing
the model files. Verify `metadata.json` and `SHA256SUMS` before running.

## Replay gate

```bash
PYTHONPATH=src python scripts/run_phase5.py replay \
  --runtime onnx --model artifacts/deploy/yolov8n/onnx/best.onnx \
  --input .runtime/parity-set --output .runtime/pi-replay/onnx
PYTHONPATH=src python scripts/run_phase5.py replay \
  --runtime ncnn --model artifacts/deploy/yolov8n/ncnn/best_ncnn_model \
  --input .runtime/parity-set --output .runtime/pi-replay/ncnn
PYTHONPATH=src python scripts/run_phase5.py replay \
  --runtime tflite --model artifacts/deploy/yolov8n/tflite/model_float32.tflite \
  --input .runtime/parity-set --output .runtime/pi-replay/tflite
```

## Live and sustained gates

Run the camera pipeline for 30 minutes for each selected runtime, keeping each
run's report separate. The queue keeps only the latest frame.

```bash
PYTHONPATH=src python scripts/run_phase5.py camera \
  --runtime onnx --model artifacts/deploy/yolov8n/onnx/best.onnx \
  --device /dev/video0 --camera-width 1280 --camera-height 720 \
  --camera-fps 30 --duration-seconds 1800 \
  --output artifacts/benchmarks/pi5-cpu/onnx/<run-id>

python scripts/benchmark_phase6.py --runtime onnx \
  --model artifacts/deploy/yolov8n/onnx/best.onnx \
  --input .runtime/parity-set --warmup 200 --frames 1000 \
  --run-id <run-id> --output-root artifacts/benchmarks/pi5-cpu
```

Repeat the benchmark command for NCNN and TFLite. Only after all three reports
are `DONE_PI` and the camera report is `DONE` may promotion be attempted:

```bash
python scripts/promote_pi_release.py \
  --camera-report artifacts/benchmarks/pi5-cpu/onnx/<run-id>/camera_report.json \
  --run-id <run-id>
```
