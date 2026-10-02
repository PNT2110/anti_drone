# Pi 5 execution status

Status: `DONE`

Last updated: `2026-09-21 00:28 Asia/Ho_Chi_Minh`

This is a living execution log for Phases 4–7. It records commands and measured
evidence as they are completed on the Raspberry Pi 5. Credentials are never
stored in this file.

## Target device

- Host: `192.168.1.118`
- Architecture: `aarch64`
- OS: Debian GNU/Linux 13 (trixie)
- Kernel: `6.18.34+rpt-rpi-2712`
- Memory: 4.0 GiB
- Camera: USB UVC camera at `/dev/video0`, 1920×1080 MJPG
- Runtime staging directory: `/home/pi5/anti_drone_runs/20260920-yolov8n`

## Completed work

### Phase 4 — export and parity

- Release checkpoint: `yolov8n`.
- ONNX, NCNN and TFLite artifacts were exported locally.
- Local parity completed on 8 fixed images within the configured tolerance.
- Bundle created and transferred to Pi.
- Bundle SHA256 verified on Pi:
  `890710e1d742224ac60760e3ecc0c013745b9592168b7f08469be62f6a1e59fe`.

### Phase 5 — Pi runtime setup

- Pi virtual environment created at `.venv-pi`.
- Installed and imported on Pi: OpenCV, ONNX Runtime, NCNN and LiteRT.
- The PyPI `tflite-runtime` wheel was unavailable for Python 3.13/aarch64;
  the runtime uses the installed `ai-edge-litert` fallback supported by the
  application code.
- Replay passed on Pi for all three runtimes, 8 frames each:
  - ONNX: mean latency ~154.9 ms
  - NCNN: mean latency ~78.9 ms
  - TFLite/LiteRT: mean latency ~137.4 ms
- Camera pipeline was patched to write `runtime.log` incrementally and flush
  each processed frame, so `tail -f` shows live progress.

### Pi remote display access

- RealVNC service mode is active on port `5900`.
- The physical-screen access profile is:
  `VNC / 192.168.1.118:5900`.
- XRDP remains available on port `3389` for a separate desktop session; it is
  not the physical-screen view.

## Current execution

### ONNX live camera gate

- Status: `DONE`.
- Required duration: 1800 seconds.
- Output: `.runtime/pi-camera/onnx/` on the Pi.
- Live log: `.runtime/pi-camera/onnx/runtime.log`.
- The run reached the 30-minute gate with live frames and no camera capture
  error; the orchestrator moved to the ONNX benchmark.

### ONNX Pi benchmark

- Status: `DONE_PI`.
- The benchmark completed on the Pi with the required 200 warm-up and 1000
  measured frames. It was substantially slower than the host reference, so it
  was allowed to finish rather than being interrupted.
- Output directory: `artifacts/benchmarks/pi5-cpu/onnx/20260920-pi5/` on the Pi.
- Measured on Pi: model-only mean `7.10 FPS`, end-to-end mean `6.77 FPS`,
  `1000` measured frames, `0` dropped frames.

### NCNN live camera gate

- Status: `DONE`.
- Output: `.runtime/pi-camera/ncnn/` on the Pi.
- Live log: `.runtime/pi-camera/ncnn/runtime.log`.
- Duration: `1800.0458` seconds
- Processed frames: `20949`
- Capture errors: none
- Dropped source frames: `25218` (the pipeline intentionally keeps only the
  newest frame instead of building an unbounded queue)

### NCNN Pi benchmark

- Status: `DONE_PI`.
- Model-only mean: `14.20 FPS`.
- End-to-end mean: `12.85 FPS`.
- End-to-end p95: `81.13 ms`.
- Frames: `1000`; dropped frames: `0`.
- RSS peak: `211.6 MB`; maximum recorded temperature: `47.4°C`.

### TFLite/LiteRT live camera gate

- Status: `DONE`.
- Output: `.runtime/pi-camera/tflite/` on the Pi.
- Live log: `.runtime/pi-camera/tflite/runtime.log`.
- Duration: `1800.1797` seconds.
- Processed frames: `12770`.
- Capture errors: none.
- Dropped source frames: `18118` because the pipeline keeps only the newest
  frame to bound latency.

### TFLite/LiteRT Pi benchmark

- Status: `DONE_PI`.
- Model-only mean: `7.76 FPS`.
- End-to-end mean: `7.35 FPS`.
- End-to-end p95: `138.79 ms`.
- Frames: `1000`; dropped frames: `0`.
- RSS peak: `296.2 MB`; maximum recorded temperature: `52.35°C`.

### Automated sequence

The Pi completed the following sequence detached from SSH/Remmina:

1. ONNX camera gate — complete.
2. ONNX benchmark — complete.
3. NCNN camera gate — complete.
4. NCNN benchmark — complete.
5. TFLite/LiteRT camera gate — complete.
6. TFLite/LiteRT benchmark — complete.

Main Pi job log:

```text
/home/pi5/anti_drone_runs/20260920-yolov8n/.runtime/pi5_phase4to6.log
```

## Final evidence

- All three camera reports are `DONE` and at least 1800 seconds:
  - ONNX: `1800.1627 s`
  - NCNN: `1800.0458 s`
  - TFLite/LiteRT: `1800.1797 s`
- All three Pi benchmarks are `DONE_PI` with 1000 measured frames.
- Release promotion: `RELEASE_CANDIDATE` for run `20260920-pi5`.
- Independent verifier: `COMPLETE`, `failures=[]`.
- Dataset v1 manifest still matches Phase 3 provenance.
- Local runtime tests: `3 passed`; patched scripts compile successfully.
- Pulled evidence is stored under:
  - `artifacts/benchmarks/pi5-cpu/<runtime>/20260920-pi5/`
  - `.runtime/pi-camera/<runtime>/`
  - `.runtime/pi-replay/<runtime>/`

## Pi benchmark summary

| Runtime | Model-only mean | End-to-end mean | End-to-end p95 | Max temp | RSS peak |
|---|---:|---:|---:|---:|---:|
| ONNX | 7.10 FPS | 6.77 FPS | 154.81 ms | 53.45°C | recorded in report |
| NCNN | 14.20 FPS | 12.85 FPS | 81.13 ms | 47.40°C | 211.6 MB |
| TFLite/LiteRT | 7.76 FPS | 7.35 FPS | 138.79 ms | 52.35°C | 296.2 MB |

For this Pi 5 CPU measurement, NCNN is the fastest measured deployment
profile. These are actual Pi results at input size 640; they are not host
reference estimates.

## Live commands

From a terminal:

```bash
ssh pi5@192.168.1.118
tail -f /home/pi5/anti_drone_runs/20260920-yolov8n/.runtime/pi5_phase4to6.log
tail -f /home/pi5/anti_drone_runs/20260920-yolov8n/.runtime/pi-camera/onnx/runtime.log
```
