# Scope 19 — Export report

Overall export status: **PARTIALLY_COMPLETE**. All six checkpoints exported successfully to float32 ONNX and NCNN. TFLite export is recorded as blocked; no placeholder artifact was treated as valid.

| Runtime | Status | Count |
|---|---|---:|
| `ncnn` | `EXPORTED` | 6 |
| `onnx` | `EXPORTED` | 6 |
| `tflite` | `BLOCKED` | 6 |

Output root: `/run/media/pnt/APP/anti_drone/artifacts/exports/scope19`

The blocked TFLite error is:

`ImportError: cannot import name 'ScalingType' from 'torch.nn.functional' (/home/pnt/miniconda3/envs/antidrone/lib/python3.12/site-packages/torch/nn/functional.py)`

The six source checkpoints are copied to a temporary directory before export, so their Scope 18 files are not modified. Input shape is static NCHW `[1, 3, imgsz, imgsz]`; batch is 1; NMS is disabled in the exported graph.

## Tensor contract

| Run | ONNX input | ONNX output | NCNN native names |
|---|---|---|---|
| `scope18-yolo26n-480` | `images` `[1, 3, 480, 480]` | `output0` `[1, 300, 6]` | `['in0']` / `['out0']` |
| `scope18-yolo26n-640` | `images` `[1, 3, 640, 640]` | `output0` `[1, 300, 6]` | `['in0']` / `['out0']` |
| `scope18-yolov11n-480` | `images` `[1, 3, 480, 480]` | `output0` `[1, 5, 4725]` | `['in0']` / `['out0']` |
| `scope18-yolov11n-640` | `images` `[1, 3, 640, 640]` | `output0` `[1, 5, 8400]` | `['in0']` / `['out0']` |
| `scope18-yolov8n-480` | `images` `[1, 3, 480, 480]` | `output0` `[1, 5, 4725]` | `['in0']` / `['out0']` |
| `scope18-yolov8n-640` | `images` `[1, 3, 640, 640]` | `output0` `[1, 5, 8400]` | `['in0']` / `['out0']` |

ONNX shapes are read from the graph. NCNN names are read from `model.ncnn.param` and static image/batch metadata; native output dimensions are deliberately not inferred without executing the native binding. Full machine-readable record: `/run/media/pnt/APP/anti_drone/.runtime/scope19/backend_contracts.json`.
