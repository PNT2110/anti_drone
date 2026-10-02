# Scope 04 — Annotation Alignment Report

## Status

`PASS` for source-box parsing and frame alignment.

## Verified mapping

| Source | Verified value |
|---|---|
| Video frames | 301, decoded 301/301 |
| MATLAB `LabelData` rows | 301 |
| Source frame index | 0–300 |
| Manifest frame ID | 1–301 |
| Timestamp source | MATLAB millisecond vector / 1000 |
| Video FPS | 30.0 |
| Resolution | 640×512 |
| Mapping rule | `frame_id = LabelData row index + 1`; `source_frame_index = row index` |

The first source timestamp is zero and the last is 10,000 ms. It aligns with
the prepared manifest timestamps at a tolerance below 1e-4 seconds. No offset
was guessed or silently applied; the converter rejects an offset or timestamp
mismatch.

## Coordinate conversion

The source `DRONE` arrays have four pixel values in MATLAB `Rectangle` form:
`x, y, width, height`. This is confirmed by the serialized `Rectangle` type
metadata and by the data itself: interpreting the third and fourth values as
`x2,y2` would produce invalid boxes such as `x2 < x1` in the first frame.

The exported source-box rule is:

```text
x1 = x
y1 = y
x2 = x + width
y2 = y + height
```

All 301 converted boxes are finite, positive and inside 640×512. No clipping
was performed.

## Output

`data/tracking_eval/sequence_001/annotations/source_boxes.csv` contains 301
rows with this schema:

```text
sequence_id,frame_id,source_label,x1,y1,x2,y2,source_annotation_reference
```

It intentionally contains no `track_id`. The official
`annotations/ground_truth.csv` remains schema-only and empty until manual
identity review is complete.
