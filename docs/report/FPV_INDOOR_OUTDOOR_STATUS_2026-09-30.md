# FPV indoor/outdoor training status — 2026-09-30

## Current state

- Server training run: `fpv-indoor-outdoor-v1`.
- Training was resumed from `last.pt`, not restarted from the base model.
- Current process: remote PID `66295`.
- Last observed progress: epoch 14/30, approximately 934/6531 training batches.
- Existing checkpoint files: `best.pt` and `last.pt`.
- Web and Pi 5 assets were not modified.

## Dataset state

- Canonical local dataset: `data/data_train`.
- Verified before archive ingestion: 94,232 images and 94,232 labels.
- `data/processed/drone-live-camera-v1` was cleaned to 733 matched image/label pairs.
- One unmatched image member was removed from `Drone-vs-Bird.tar`; `my_dataset.tar.xz` was excluded from cleanup.
- Archive ingestion was paused before completion and must be resumed only after checking its partial output.

## Pending verification

- Complete the archive-to-`data_train` ingestion for validated DUT-Anti-UAV and UAV-CB samples.
- Re-audit all image/label pairs and update the dataset manifest.
- Finish training, run locked test evaluation, export model formats, and update the web model.
