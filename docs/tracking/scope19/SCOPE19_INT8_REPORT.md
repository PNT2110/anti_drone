# Scope 19 — INT8 report

Status: **BLOCKED**. A deterministic calibration manifest with 128 images from the V3 `train` split was prepared at `/run/media/pnt/APP/anti_drone/.runtime/scope19/calibration_manifest.json`. It does not use V3 test data.

All six requested INT8 TFLite exports were attempted and all six were blocked by the same environment/toolchain incompatibility:

`ImportError: cannot import name 'ScalingType' from 'torch.nn.functional' (/home/pnt/miniconda3/envs/antidrone/lib/python3.12/site-packages/torch/nn/functional.py)`

No INT8 artifact, size, checksum, or accuracy claim is fabricated. INT8 remains unvalidated and cannot be used as a model-selection tie-breaker in this scope.
