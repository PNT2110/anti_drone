# Scope 11 — Quarantine Provenance Report

## Accounting result

All 6,505 quarantined samples and all 4,172 quarantined groups have exactly one row in `.runtime/scope11/quarantine_provenance.csv`.

| Provenance status | Samples | Groups affected | Interpretation |
|---|---:|---:|---|
| `CONFIRMED_SOURCE_SEQUENCE` | 0 | 0 | No archive tracking member matched the prepared image hash uniquely. |
| `CONFIRMED_INDEPENDENT_IMAGE` | 0 | 0 | No explicit independence metadata was found. |
| `POSSIBLE_MATCH` | 0 | 0 | Filename candidates were not promoted; no ambiguous exact content match occurred. |
| `UNRESOLVED` | 6,505 | 4,172 | Evidence is insufficient for a stronger claim. |

The zero confirmed-source result is a conservative content result, not proof that the samples are independent or non-temporal.

## Evidence by source

### DUT / `base` — 4,171 samples

All 4,171 prepared images matched their expected DUT detection archive member and V1 image hash. The corresponding detection XML member exists. The archive contains tracking sequences with `videoNN` and frame indices, so the audit additionally hashed all tracking JPG members and compared their content hashes globally. No tracking JPG matched any quarantined prepared-image hash.

Filename/frame-number candidates existed for 3,256 rows (32,736 candidate member references in total); these are only clues. They did not become `POSSIBLE_MATCH` or `CONFIRMED_SOURCE_SEQUENCE` because no exact content match was found. The absence of an exact match is not evidence of temporal independence.

### `my_dataset` — 2,334 samples

2,334 images matched `my_dataset/<basename>.jpg` by exact archive-member and image hash. 2,327 corresponding `.txt` annotation members were present. The archive is flat and supplies no verifiable source video, session, or frame-index key. Consequently these samples remain `UNRESOLVED`; they are not declared `CONFIRMED_INDEPENDENT_IMAGE`.

## Reproducibility and limits

The mapping is content-based where the archive provides image bytes. No pHash or filename match was used as confirmation. No source images, labels, V1/V2 manifests, checkpoint, or split assignment were changed. The mapping does not prove source-sequence disjointness, and does not authorize a new split or training run.

Machine-readable evidence: `.runtime/scope11/quarantine_provenance.csv`, `.runtime/scope11/quarantine_provenance_summary.json`.
