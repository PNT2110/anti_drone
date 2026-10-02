# Pi 5 tracking runbook

## Install and inspect

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Confirm that the selected exported model is present and that the chosen
runtime matches its export. Do not run the ONNX/NCNN/LiteRT model through a
different preprocessing contract without documenting it.

## Replay first

```bash
python scripts/run_phase5.py replay \
  --runtime onnx --model /path/to/model.onnx \
  --input /path/to/replay-images --output runs/pi5-replay \
  --tracker bytetrack_motion_adaptive --source-fps 30
```

Check `replay_report.json`, `environment.json`, and `runtime.log`. Confirm
that IDs remain stable through short gaps, low-confidence detections attach to
existing tracks, and predicted boxes do not generate alerts.

## USB camera

```bash
python scripts/run_phase5.py camera \
  --runtime onnx --model /path/to/model.onnx \
  --output runs/pi5-camera --device /dev/video0 \
  --tracker bytetrack_motion_adaptive --duration-seconds 30
```

Use `--show-overlay` only for supervised diagnostics. Confirm camera
reconnect behavior, source-frame gaps, `capture_errors`, and actual end-to-end
latency from the JSONL log. Keep the alert sink integration and hardware
actuator policy outside this tracker implementation.

## Evidence to archive

Archive the model checksum, `environment.json`, `runtime.log`, report JSON,
selected tracker YAML, command line, and host/Pi information. Clearly label
whether each result is replay, tracking-only, or live camera evidence.
