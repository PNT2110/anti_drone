# Scope 12 — Training Readiness

## Environment and model support

The actual `antidrone` environment was used for the loader smoke test:

- Python 3.12.14
- Ultralytics 8.4.125
- Torch 2.8.0+cu129
- CUDA 12.9
- NVIDIA GeForce RTX 3060, CUDA available

All three exact repository weights loaded as detection models without training:

| Repository model ID | Weight | SHA-256 |
|---|---|---|
| `yolov8n` | `/home/pnt/Desktop/antidrone/model/yolov8n.pt` | `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` |
| `yolov11n` | `/home/pnt/Desktop/antidrone/model/yolo11n.pt` | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` |
| `yolo26n` | `/home/pnt/Desktop/antidrone/model/yolo26n.pt` | `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef` |

Prepared, but not run, configurations are in `configs/training/scope12/`:

- YOLOv8n × 640 and × 480;
- YOLOv11n × 640 and × 480;
- YOLOv26n × 640 and × 480.

Each configuration pins the executable `data.yaml`, V2 manifest/registry hashes, seed 42, image size, batch 16, device 0, workers 4, a unique output directory, exact weight hash, and a resume rule that only resumes that configuration's own `last.pt`. No epoch, validation run for model selection, or checkpoint update was executed.

The test split is held out. The configuration permits validation-only checkpoint/parameter selection. Halmstad videos are not in this executable dataset and are not claimed independent from V1 or from a future checkpoint.

## Readiness decision

**READY FOR A CONTROLLED NEW TRAINING RUN technically; NOT source-independent and NOT approval to train automatically.** The dataset and loader are executable, but archive-level provenance for the 318 groups is incomplete and 47 candidate session prefixes cross splits. Research & Design must decide whether the accepted group contract is sufficient or require source-session disambiguation before training.
