# Scope 03 — Identity Annotation Guide

## Purpose

The detector dataset has class labels, while MOT evaluation needs a stable
`track_id` for the same physical object across consecutive frames. These are
different labels. Do not copy a detector output ID into ground truth.

## CSV schema

`data/tracking_eval/sequence_001/annotations/ground_truth.csv` uses one row per
object per frame:

```text
sequence_id,frame_id,track_id,class_id,x1,y1,x2,y2
halmstad_v_drone_001,1,1,0,136,23,191,61
```

Rules:

1. `frame_id` is the one-based ID in `frame_manifest.csv`.
2. `track_id` is a positive integer stable for the entire selected sequence.
3. `class_id` must be `0` (`drone`).
4. Coordinates are absolute pixels, with `0 <= x1 < x2 <= width` and
   `0 <= y1 < y2 <= height`.
5. Keep occluded or temporarily missed objects as annotations only when the
   source evidence supports the identity; do not interpolate unsupported boxes.
6. Review the whole sequence for ID switches, duplicate IDs in one frame,
   truncation and out-of-frame boxes.

## Verification workflow

1. Decode the original video and inspect all 301 frames in order.
2. Use the MATLAB sidecar as a source hint, then manually verify the box and
   identity association in the video.
3. Write only human-verified rows to `ground_truth.csv`.
4. Run:

   ```bash
   python scripts/validate_tracking_annotations.py \
     --manifest data/tracking_eval/sequence_001/frame_manifest.csv \
     --annotations data/tracking_eval/sequence_001/annotations/ground_truth.csv \
     --output data/tracking_eval/sequence_001/validation_report.json
   ```

5. Use `--identity-verified` only after an independent human review. The flag
   records the review claim; it does not replace the review.

Until this is complete, the sequence is not valid ground truth for HOTA, IDF1
or IDSW. The current empty file is intentional and is reported as
`DATA READY — IDENTITY ANNOTATION PENDING`.
