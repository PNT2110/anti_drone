# Scope 20 — INT8 report

Status: **INT8_BLOCKED**. The locked calibration membership is 128 `train` images for each 480/640 representation; no val/test samples were used. Calibration arrays are NCHW float32 in `[0,1]`, with hashes and sample IDs in `/run/media/pnt/APP/anti_drone/.runtime/scope20/int8_calibration.json`.

| Model | Status | Source ONNX SHA-256 | Converter copy mutated only |
|---|---|---|---|
| `scope18-yolo26n-480` | `BLOCKED` | `1450011ffa350198c1ff352cfbc1309b425f8f6d749e75dfe61cd58d84068175` | True |
| `scope18-yolo26n-640` | `BLOCKED` | `73ec16af24e0642e06432f7a3288a812664cdb760c2f44913982bfd74fdcefde` | True |
| `scope18-yolov11n-480` | `BLOCKED` | `34482189970fafca87f096e5006f3b283086a113fd4a3bea168adaf9aba3db04` | True |
| `scope18-yolov11n-640` | `BLOCKED` | `bfc7a68f5b01f500715263d7f4026498d80e2d513e0792d1f6b539a1ed1e5e92` | True |
| `scope18-yolov8n-480` | `BLOCKED` | `e1b7ce73354e7d0674170984410605fe78ee3110e46ccb1f62a4bbbaf9fba034` | True |
| `scope18-yolov8n-640` | `BLOCKED` | `ef1293a0f80ad05ce826620e7bd329d066df5caac7b892f9cd11e174a320e6f5` | True |

All six full-integer attempts produced no valid INT8 artifact. The observed failure is: `tflite/kernels/conv.cc:372 filter->dims->data[0] % data->groups != 0 (16 != 0) — the calibration interpreter failed to prepare CONV_2D during strict full-integer quantization.`. The alternative TensorFlow converter is blocked by missing `tf_keras`. Scale/zero-point, output dtype, INT8 size and INT8 parity are therefore **N/A**, not fabricated.

Float conversion evidence (not an INT8 deployment claim):

- `/run/media/pnt/APP/anti_drone/artifacts/exports/scope20/scope18-yolov8n-480/float32_onnx2tf/model_float16.tflite` — `2e22a6d7d573443e47f19343f79c7f3d4b411e99e3c635885203452ea985c73b`, 6127844 bytes
- `/run/media/pnt/APP/anti_drone/artifacts/exports/scope20/scope18-yolov8n-480/float32_onnx2tf/model_float32.tflite` — `bbf61d9b5d4a2df43f3ae2b72164ac15c3d72cbc4e1cacb2b9901cde263786eb`, 12185168 bytes
- `/run/media/pnt/APP/anti_drone/artifacts/exports/scope20/scope18-yolov8n-480/float32_onnx2tf/scope18-yolov8n-480_float16.tflite` — `7115021c011aee4a31e8f2e45c280f8dced937b795fd7c23c98d3cc9cc97d0d1`, 6127856 bytes
- `/run/media/pnt/APP/anti_drone/artifacts/exports/scope20/scope18-yolov8n-480/float32_onnx2tf/scope18-yolov8n-480_float32.tflite` — `3b023debf1591716963393a3712f087b2fdfe7908ca1f2bb2f07d6beed1039b2`, 12185180 bytes

No INT8 backend is marked READY.
