# Scope 02 runtime parity report

## Method

ONNX and NCNN used the same model family, 640 export input, letterbox/RGB/
pixel-255 preprocessing, confidence 0.10, NMS IoU 0.70, and the same eight
parity images. Detector outputs were cached independently with
`scripts/cache_detections.py`; comparison was per frame and per ordered
detection after decoder/NMS.

## Fresh host result

```text
frames compared:          8
per-frame count equality: PASS
class equality:           PASS
paired detections:         3
max abs confidence delta:  0.0000006855
max abs box pixel delta:   0.0001220703
```

The configured existing gates are confidence `0.05`, box `5.0` pixels, and
exact class ID. The fresh host result is within all gates. The complete cache
files are:

```text
.runtime/scope01/detection-cache/onnx_parity_8frames.jsonl
.runtime/scope02/detection-cache/ncnn_parity_8frames.jsonl
```

## Interpretation

This is a host x86_64 parity result, not a Pi result. It does not prove equal
CPU performance, memory behavior, thermal behavior, or Python wheel behavior
on aarch64. The existing model metadata links both exports to the same source
checkpoint SHA; serialized ONNX and NCNN hashes remain different by design.

No tiny-object pixel-center analysis beyond the three detections was claimed,
and no threshold was tuned to improve parity.

## Status

`PASS` for fresh host parity. `BLOCKED` for Pi-side parity reproduction.
