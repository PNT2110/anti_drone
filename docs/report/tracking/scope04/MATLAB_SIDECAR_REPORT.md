# Scope 04 — MATLAB Sidecar Report

## Status

`PASS` for structural parsing and source-box extraction.

`IDENTITY ANNOTATION PENDING` because the sidecar has no source track ID.

## File structure

| Field | Observed value |
|---|---|
| MAT format | MATLAB v5 |
| Endianness/version | little-endian `IM`, version `0x0100` |
| Header date | 30-Mar-2020 15:02:27 |
| MATLAB platform | PCWIN64 |
| Saved object | MCOS opaque `groundTruth` |
| Nested workspace | `FileWrapper__` serialized workspace |
| Source path in sidecar | `C:\Data\Video_V\V_DRONE_001.mp4` |
| MATLAB release metadata | Computer Vision Toolbox 9.1, R2019b |

The top-level `gTruth` is not a classic MATLAB struct that SciPy can read
directly. The converter reconstructs the nested serialized workspace, finds
the `groundTruth` fields, and does not alter the original `.mat` file.

## Ground truth fields

- `DataSource`: source path and a 301-entry timestamp vector;
- `LabelDefinitions`: `AIRPLANE`, `BIRD`, `DRONE`, `HELICOPTER`;
- `LabelData`: 301 rows with fields `Time`, `AIRPLANE`, `BIRD`, `DRONE`,
  `HELICOPTER`;
- `Version`: Computer Vision Toolbox provenance.

The source timestamp vector is 0.0000–10,000.0000 ms with a 33.3333 ms
median step. Each `LabelData` row has one `DRONE` rectangle; the other three
classes are empty in every row. No frame has multiple drone boxes.

## Identity conclusion

There is no `track_id`, object identity field, or identity event metadata in
the parsed `LabelData` structure. The sidecar provides per-frame class boxes,
not identity ground truth. Therefore verified track IDs: **0**.
