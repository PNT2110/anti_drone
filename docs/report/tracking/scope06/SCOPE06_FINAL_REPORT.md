# Scope 06 — Final Report

## Final status

`COMPLETE — HUMAN REVIEW VERIFIED; SPLIT UNVERIFIED`

The review tooling, evidence schema, segment validation, read-only frame-step
viewer, and ground-truth export guard are implemented, tested, and applied to
the user's direct review confirmation.

## Required answers

1. **Review package ready?** Yes. It contains the 301-frame overlay, source
   boxes, per-frame preparation manifest, five-segment evidence template,
   workflow instructions, validator, and pause/step viewer.
2. **Frames human-reviewed?** 301, based on the user's direct confirmation.
3. **Frames PENDING?** 0.
4. **Verified track IDs?** 1 (`track_id=1`).
5. **Official GT rows?** 301.
6. **Validation result?** `PASS`; export completed.
7. **Batch evidence?** Five non-overlapping `VERIFIED` segments cover frames
   1–301, each with reviewer reference `user`.
8. **Split/provenance status?** `SPLIT_UNVERIFIED`. There is **NO NEW SOURCE
   PROVENANCE EVIDENCE** in Scope 06.
9. **Metrics run?** No HOTA, IDF1, or IDSW; no tracker or model changes.
10. **Tests?** 36 passed, 1 skipped because `cv2` is unavailable in the
    current environment. GT integrity checks also passed: 301 unique frames,
    all `track_id=1`, all `class_id=0`, boxes equal to source boxes.

## Commands and changed files

Commands run:

```text
python scripts/validate_identity_review.py --help
python scripts/validate_identity_review.py --review-manifest ... --evidence ... --source-boxes ... --manifest ... --ground-truth ... --output ...
python scripts/validate_identity_review.py --review-manifest ... --evidence ... --source-boxes ... --manifest ... --ground-truth ... --output ... --export-ground-truth
python scripts/validate_tracking_annotations.py --manifest ... --annotations ... --output ... --identity-verified
python -m compileall -q scripts src tests
git diff --check
python -m pytest -q
```

User-review data and generated artifacts changed:

- `review/identity_review_evidence.csv` — five `VERIFIED` segments, ID 1;
- `annotations/ground_truth.csv` — exported 301-row official GT;
- `review/identity_review_validation.json` — validator `PASS`;
- `review/ground_truth_validation.json` — annotation validator `PASS`;
- `review/identity_review_summary.json` and `sequence.json` — verified state;
- `review/identity_review_evidence.csv.bak-20260922T135731+0700` — pre-edit backup.

The video, MATLAB sidecar, and source boxes were not edited. No commit or push
was performed.

## Checksums

```text
8e779fcec9506f8fcbbd16130d4f82f90c02ca28319180c4bf5d967569db9d3c  annotations/source_boxes.csv
ed76a514237e2e45ed424fc81349b5dbb4e493a1166ecb1116051f3e25abf547  annotations/ground_truth.csv
95ec6c8d08118a6d000cd87c33e1414f7234434c2b5ceab46d9b56a4af0c9624  review/source_boxes_overlay.mp4
2fed55400b4b7e27a028c1fa4818ca4f5e1c89e41dbd37a2ed46715e5a3e3e2b  review/identity_review_manifest.csv
ff9f091567f6eff4e8ca8a43ffcb89b88713c873232fcae1acd58297212876f5  review/identity_review_evidence.csv
bbd4645c04b9bb4540407d8ce61b566d8dad765306ff8348349d9e53382b6c67  review/identity_review_validation.json
18970812dc285cf125079281fc7b1d0b0a95fba1754c25932ae0cdb157f9d691  review/ground_truth_validation.json
a429278574da151d1cd79ce3db48adc4369c2a5b8ddc8658fafda4f043f6ee92  review/identity_review_summary.json
7455a6783af8d6cd66823960f620cdb0dee02e1a26220a6ac494f444303cc403  sequence.json
a404f631eadd863ec1557c1dc516281062235137e740d2789528897f407a22d9  review/identity_review_evidence.csv.bak-20260922T135731+0700
```

## Scope boundaries preserved

No source video or sidecar was modified. No dataset split, checkpoint,
threshold, tracker, training configuration, or Raspberry Pi runtime was
changed. No unverified identity was promoted to official ground truth.
