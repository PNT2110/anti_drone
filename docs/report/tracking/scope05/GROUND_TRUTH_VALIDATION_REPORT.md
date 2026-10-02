# Scope 05 — Ground Truth Validation Report

## Status

`IDENTITY ANNOTATION PENDING`

The official `annotations/ground_truth.csv` remains a schema-only file with
zero data rows. This is intentional: a complete 301-row source-box file is
not identity ground truth until an independent human review establishes stable
physical-object IDs.

## Current checks

| Check | Result |
|---|---:|
| Source-box rows | 301 |
| Source-box frame coverage | 1–301 |
| Review-manifest rows | 301 |
| Review status | 301 PENDING |
| Official GT rows | 0 |
| Verified track IDs | 0 |
| Missing source annotations | 0 |
| Invalid source boxes | 0 |
| Official GT validator | `DATA READY — IDENTITY ANNOTATION PENDING` |
| Identity-review validator | `IDENTITY ANNOTATION PENDING` |

The Scope 03 validator still checks the official GT schema, frame IDs, class
IDs and geometry. The Scope 05 review validator additionally checks review
schema, status transitions, duplicate frame IDs, source-box provenance and
coverage. Export is permitted only when every row is `VERIFIED` with a positive
candidate identity and review note.

## Ground-truth export rule

When review is complete:

```bash
python scripts/validate_identity_review.py \
  --review-manifest data/tracking_eval/sequence_001/review/identity_review_manifest.csv \
  --source-boxes data/tracking_eval/sequence_001/annotations/source_boxes.csv \
  --manifest data/tracking_eval/sequence_001/frame_manifest.csv \
  --ground-truth data/tracking_eval/sequence_001/annotations/ground_truth.csv \
  --output data/tracking_eval/sequence_001/review/identity_review_validation.json \
  --export-ground-truth
```

Until then, the command reports pending and leaves the official GT unchanged.
