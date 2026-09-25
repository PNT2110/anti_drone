# Scope 02 model artifact report

## Selected artifacts

The validation used the existing 640 export set:

```text
artifacts/deploy/yolov8n/onnx/best.onnx
artifacts/deploy/yolov8n/ncnn/best_ncnn_model/model.ncnn.param
artifacts/deploy/yolov8n/ncnn/best_ncnn_model/model.ncnn.bin
```

No model was downloaded, retrained, or re-exported.

## Metadata

`artifacts/deploy/yolov8n/metadata.json` reports:

- model: YOLOv8n, one class (`0: drone`);
- input: 640x640, NCHW float32, RGB, pixel/255, letterbox;
- source checkpoint SHA256:
  `662fbc1c066041345970f4211a6ceb9209907a331fd1724c0b2be7e53a4beec1`;
- ONNX export SHA256 recorded by metadata:
  `2a8491c8b3935596b94bf5e268292491d289bb51ac9065a28d0f8a562250097d`;
- NCNN export directory SHA256 recorded by metadata:
  `9e4d4d9d6f2982cbcd71b3b9f2a1d77acb1fb3f00702d423b9b438bdf5e5cc29`.

The individual NCNN file hashes currently present are:

```text
model.ncnn.param 47a0c16d6d929989db921482e302ba9e2a27295bfcc436fbaedd3e48299a5ea1
model.ncnn.bin   c28f2cd199d3c867e438d5847d85715c9860aa93eea61a8f78ecbb4e325baaeb
```

The metadata asserts that ONNX and NCNN derive from the same source checkpoint;
their export file hashes are naturally different. This is not a claim of
bit-identical serialized models.

## Runtime inspection

ONNX Runtime loaded the model and reported:

```text
input  images  [1, 3, 640, 640]  tensor(float)
output output0 [1, 5, 8400]       tensor(float)
```

The NCNN artifact loaded successfully with NCNN Python 1.0.20260526 on the
host. Its repository metadata reports the same 640 input, one-class detect
head, and three-channel input.

## Existing parity evidence

The repository's existing `artifacts/deploy/yolov8n/parity.json` records class
exactness and prior max differences within the configured gates. Scope 02 also
performed a fresh host comparison from the same eight-image parity set; the
fresh result is in `docs/tracking/scope02/RUNTIME_PARITY_REPORT.md` and does
not claim Pi equivalence.
