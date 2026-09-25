# Scope 03 — Data Validation Report

## Result

`DATA READY — IDENTITY ANNOTATION PENDING`

The temporal source is valid and reproducible, but verified identity ground
truth is not yet present. The current split is also
`SPLIT_UNVERIFIED` because the existing image registry distributes some source
groups across train/validation/test.

## Sequence checks

| Check | Result |
|---|---:|
| Manifest rows | 301 |
| Unique frame IDs | 301 |
| Frame ordering | pass, 1–301 |
| Source frame indices | pass, 0–300 |
| Timestamp source | source video FPS |
| Timestamp range | 0.000000000–10.000000000 s |
| Timestamp monotonicity | pass |
| Resolution consistency | pass, 640 × 512 |
| Container vs decoded frame count | pass, 301 vs 301 |
| Missing/truncated decoded frames | 0 |
| Annotation rows | 0 |
| Verified identity tracks | 0 |

## Validator output

The validator found no schema, frame, timestamp or geometry errors. It emitted
one warning: `identity_annotation_pending`. An empty annotation file is
accepted as a preparation state, not as MOT ground truth.

## Detection cache

An ONNX detector-only cache was created for all 301 frames using
`artifacts/deploy/yolov8n/onnx/best.onnx`, input size 640, confidence 0.10 and
NMS IoU 0.70. It contains 301 frame records and 272 detector boxes. It has no
tracker IDs and must not be used as ground truth.

## Not evaluated in Scope 03

HOTA, IDF1 and IDSW were not computed. They require verified identity
annotations and are outside temporal dataset preparation.
