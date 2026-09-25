# Scope 06 — Ground-Truth Finalization Report

## Decision

Official identity ground truth was finalized after the user's direct
confirmation and a passing validator run.

Current state:

- official `annotations/ground_truth.csv`: 301 data rows;
- source annotations: 301 rows remain available in `annotations/source_boxes.csv`;
- review status: `VERIFIED`;
- verified track IDs: 1;
- all official GT rows use `track_id=1` and `class_id=0`.

The validator accepts batch evidence only when ranges are non-overlapping,
inside the source frame range, and carry the required identity/reviewer fields.
Partial, `NEEDS_REVIEW`, `REJECTED`, or otherwise unverified evidence cannot
replace the official GT. The export was performed only after all five
segments were `VERIFIED` and the validator returned `PASS`.

## Provenance

The validation report records the review-manifest SHA-256, source-box SHA-256,
and evidence-template SHA-256. This is review-artifact provenance, not source
independence evidence. There is **NO NEW SOURCE PROVENANCE EVIDENCE** in Scope
06; the Scope 05 result remains `SPLIT_UNVERIFIED`.

## Required next action

The finalized GT may now be used for the next explicitly authorized tracking
evaluation step. Data independence remains `SPLIT_UNVERIFIED`; this report does
not authorize HOTA/IDF1/IDSW or any training change.
