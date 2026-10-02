# Scope 19 — Backend parity

Parity protocol was fixed before inspection: confidence absolute difference `<= 0.05`, bounding-box IoU `>= 0.95`, exact class id, and exact detection count. Predictions use confidence `0.25`, NMS IoU `0.70`, CPU, and the same 8 deterministic `train` images for every backend.

| Runtime | Result | Count |
|---|---|---:|
| `ncnn` | `BACKEND_PARITY_FAIL` | 6 |
| `onnx` | `BACKEND_PARITY_FAIL` | 6 |
| `tflite` | `BACKEND_PARITY_FAIL` | 6 |

All six ONNX and all six NCNN runs were executable, but none passed the all-eight-image parity gate. The failures are diagnostic, not model retuning: ONNX has isolated IoU/count mismatches under the declared tolerance; NCNN is executable after the Ultralytics loader naming alias and is also marked parity-fail. TFLite was unavailable because export was blocked.

Raw artifact: `/run/media/pnt/APP/anti_drone/.runtime/scope19/backend_parity.json`. No test image or test metric was accessed.
