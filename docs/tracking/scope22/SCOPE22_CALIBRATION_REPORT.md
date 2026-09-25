# Scope 22 — Calibration report

Status: **PASS — TRAIN-ONLY CALIBRATION**.

- Manifest: `/run/media/pnt/APP/anti_drone/.runtime/scope19/calibration_manifest.json`
- Manifest SHA-256: `4c582deab8ec13a23a0ecf0b1b806e6f3dd0c2c43f5a7dca06c785227e444b59`
- Membership: 128 images, exact Scope 19/20 manifest.
- Source split: `train`.
- VAL used: no.
- TEST used: no.
- Quantization method: NCNN `method=kl` calibration table.
- Representation: RGB, zero mean, norm `1/255`, fixed size 480 or 640, thread 4.

No calibration sample was selected after inspecting INT8 results.
