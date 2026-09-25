# Scope 11 — Source Group Collision Report

## Result

No `SOURCE_GROUP_ALIAS` was established. There were no exact image-hash collisions and no exact `(source, image)` path collisions between the 6,505 quarantined samples and the 30,227 samples in the 318 verified RGBT groups.

| Check | Result |
|---|---:|
| Quarantine vs verified exact hash collisions | 0 |
| Quarantine vs verified exact source-path collisions | 0 |
| Confirmed source-sequence aliases | 0 |
| Exact duplicate hash groups inside the quarantine | 0 |
| Extra rows from exact duplicates inside the quarantine | 0 |
| Near-duplicate/pHash confirmation | Not run / not used |

The alias check only considers a source sequence key supported by an exact tracking-image hash. Since no quarantined row reached `CONFIRMED_SOURCE_SEQUENCE`, no alias can be asserted. This does not mean that two groups cannot share a source video; it means the available evidence did not prove it.

The audit distinguishes exact duplicate, same source video/session, near-duplicate suspicion, and unresolved provenance. It does not silently merge groups or edit V2.

Machine-readable evidence: `.runtime/scope11/source_group_collisions.json`.
