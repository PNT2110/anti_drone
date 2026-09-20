# anti_drone

Anti-drone detection project for Raspberry Pi 5 (4GB) and a USB camera.

Training and evaluation run on the user's CUDA GPU machine. The Raspberry Pi
only performs CPU inference, tracking, overlay and terminal logging. The
deployment profiles are ONNX Runtime, NCNN and TensorFlow Lite.

## Project scope

- One class: `0 = drone`.
- YOLO training on the GPU workstation.
- ByteTrack-based temporal tracking on the Pi.
- Multi-frame local alert state, overlay and terminal event log.
- No actuator control, guidance or weapon-control behavior.

## Phase runbooks

Follow the phase runbooks in order:

1. [Phase index](docs/phases/README.md)
2. [Repository baseline](docs/phases/PHASE_00_REPOSITORY_BASELINE.md)
3. [Dataset ingestion and audit](docs/phases/PHASE_01_DATASET_INGESTION_AND_AUDIT.md)
4. [GPU training](docs/phases/PHASE_02_GPU_TRAINING.md)
5. [Evaluation and model selection](docs/phases/PHASE_03_EVALUATION_AND_MODEL_SELECTION.md)
6. [Export and runtime parity](docs/phases/PHASE_04_EXPORT_AND_RUNTIME_PARITY.md)
7. [Pi 5 and USB camera pipeline](docs/phases/PHASE_05_PI5_USB_CAMERA_PIPELINE.md)
8. [Benchmark and release](docs/phases/PHASE_06_BENCHMARK_AND_RELEASE.md)
9. [Retraining and maintenance](docs/phases/PHASE_07_RETRAINING_AND_MAINTENANCE.md)

## Repository layout

`configs/`, `docs/`, `src/` and `tests/` are project files. Dataset copies,
runtime manifests, checkpoints and benchmark output remain local under
`data/`, `.runtime/` and `artifacts/`.

The deployment bundle is kept directly under the model directory and has one
profile per CPU runtime.

## Current Phase 4–7 status

The locked Phase 3 winner is `yolov8n`. Phase 4 export and parity are complete
for ONNX Runtime, NCNN and TFLite. Replay validation also passes for all three
profiles. The host reference benchmark used 1,000 frames after 200 warm-up
frames, but those numbers are not Pi 5 measurements.

| Phase | Status | Evidence |
|---|---|---|
| 04 export/parity | `DONE` | [`artifacts/deploy/yolov8n/`](artifacts/deploy/yolov8n/) |
| 05 replay | `DONE`; camera gate pending | [`PI5_HANDOFF.md`](docs/PI5_HANDOFF.md) |
| 06 benchmark/release | Pi gate pending | [`RELEASE_CANDIDATE.md`](artifacts/releases/yolov8n/RELEASE_CANDIDATE.md) |
| 07 maintenance | baseline frozen | [`phase7_status.json`](artifacts/maintenance/yolov8n/phase7_status.json) |

The verified Pi handoff is [anti-drone-yolov8n-pi5.tar.gz](artifacts/releases/yolov8n/anti-drone-yolov8n-pi5.tar.gz).
Run the camera and sustained benchmark gate on the actual Pi 5 before promoting
the release. The independent audit is [VERIFICATION.json](artifacts/releases/yolov8n/VERIFICATION.json).
