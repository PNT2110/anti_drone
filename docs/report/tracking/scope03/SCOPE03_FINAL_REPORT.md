# Scope 03 — Final Report

## Acceptance status

`PARTIALLY COMPLETE — SPLIT UNVERIFIED`

The repository now has one decoded, timestamped continuous sequence and a
reproducible annotation-validation path. The sequence itself is
`DATA READY — IDENTITY ANNOTATION PENDING` because the original MATLAB
sidecar has not yet been converted into manually verified identity rows.

## Delivered

- Inventoried all local dataset archives and the prepared detector manifest.
- Selected Halmstad `V_DRONE_001` as a continuous visible sequence.
- Extracted only the selected MP4 and its `.mat` sidecar.
- Verified 301/301 frames decode at 30 FPS and 640×512.
- Created an ordered frame manifest with source frame indices and timestamps.
- Implemented `scripts/validate_tracking_annotations.py` with schema, frame,
  timestamp, identity, class and bounding-box checks.
- Added validator tests for duplicate frames, non-increasing timestamps,
  missing frames, invalid boxes, duplicate identities and pending/unverified
  identity GT.
- Created a detector-only ONNX cache for all 301 frames.
- Documented the annotation schema and the split-independence limitation.

## Evidence paths

- `data/tracking_eval/sequence_001/sequence.json`
- `data/tracking_eval/sequence_001/frame_manifest.csv`
- `data/tracking_eval/sequence_001/validation_report.json`
- `data/tracking_eval/sequence_001/detection_cache.onnx.jsonl`
- `docs/tracking/scope03/DATA_INVENTORY.md`
- `docs/tracking/scope03/SELECTED_SEQUENCE.md`
- `docs/tracking/scope03/ANNOTATION_GUIDE.md`
- `docs/tracking/scope03/DATA_VALIDATION_REPORT.md`

## Remaining blockers

1. Normalize and manually verify the MATLAB `gTruth` sidecar into stable
   `track_id` rows; no pseudo IDs are acceptable.
2. Prove a sequence-level train/validation/test boundary before using this
   sequence for independent tracking evaluation. The current registry's
   group-overlap field is not sufficient evidence.
3. Only after those blockers are closed should a later scope calculate MOT
   identity metrics. No HOTA, IDF1 or IDSW was run here.

No tracker, Kalman filter, alert logic, checkpoint, training split or Pi
deployment behavior was changed by Scope 03.
