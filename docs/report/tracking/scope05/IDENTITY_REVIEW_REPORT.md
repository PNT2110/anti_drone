# Scope 05 — Identity Review Report

## Status

`HUMAN REVIEW PENDING`

The review package is ready, but no human review was performed in this
session. No `candidate_identity` or official `track_id` was populated.

| Item | Result |
|---|---:|
| Review frames prepared | 301 |
| Frames reviewed | 0 |
| Frames PENDING | 301 |
| Frames NEEDS_REVIEW | 0 |
| Verified track IDs | 0 |
| Official ground-truth rows | 0 |
| Review video frames | 301 |

## Workflow

1. Play `review/source_boxes_overlay.mp4` from beginning to end.
2. Edit `review/identity_review_manifest.csv` only after inspecting temporal
   continuity.
3. Keep `PENDING` when the identity is not reviewed, and use `NEEDS_REVIEW`
   for ambiguous disappearance, reappearance, occlusion or scene change.
4. Use `VERIFIED` only for a human-confirmed physical identity and fill a
   positive `candidate_identity` plus an evidence note.
5. Run `scripts/validate_identity_review.py`. Official GT export is blocked
   until all 301 rows are `VERIFIED`.

The workflow never uses ByteTrack output as candidate identity and never
auto-fills `track_id=1`.

## Review artifacts

- `data/tracking_eval/sequence_001/review/identity_review_manifest.csv`
- `data/tracking_eval/sequence_001/review/identity_review_summary.json`
- `data/tracking_eval/sequence_001/review/IDENTITY_REVIEW_WORKFLOW.md`
- `data/tracking_eval/sequence_001/review/source_boxes_overlay.mp4`
- `data/tracking_eval/sequence_001/review/review_cases.csv`
- `data/tracking_eval/sequence_001/review/identity_review_validation.json`
