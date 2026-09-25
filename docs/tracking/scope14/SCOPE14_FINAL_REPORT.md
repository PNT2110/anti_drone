# Scope 14 — Final Report

## Decision

**PARTIALLY COMPLETE — policy and dry-run evidence are complete; V3 is not activated.**

## Findings

1. Anti-UAV300 has a real `train/val/test` source partition: 160/67/91 sequence directories and 12,142/8,237/9,848 mapped samples. `label_new/{train,val,test}.json` agrees with the directory partition for all 318 sequences.
2. V2 currently mixes those original partitions across new splits. In particular, original test contributes 6,910 samples to V2 train and original val contributes 5,655 samples to V2 train. This is a source-boundary risk if those partitions are intended as protected holdouts.
3. No date/time prefix crosses original source partitions. There are 63 total prefixes, 59 multi-group candidates, and 47 that cross current V2 splits.
4. Option A (V2) has zero source-sequence overlap but does not provide prefix atomicity or session-disjointness.
5. Option B conservative prefix-atomic dry run has zero source-sequence/prefix/path/hash overlap and no quarantine leakage, but its protected-boundary counts are 12,142/8,237/9,848 rather than 70/20/10.
6. A seed-42 target-ratio preview would violate the protected original boundary for 43 candidate prefixes / 18,030 samples, so it is blocked and not used.
7. Session independence remains unverified. Equal timestamps are not treated as shared sessions, and different prefixes are not treated as independent sessions.

## Required status distinction

- `CONFIRMED_SOURCE_SEQUENCE_DISJOINT`: true for Option A and conservative Option B.
- `CANDIDATE_PREFIX_DISJOINT`: false for A; true for conservative B.
- `SESSION_DISJOINT_UNVERIFIED`: true for both.

No V3 production split, image copy, `data.yaml`, training run, or checkpoint change was created. The 6,505 quarantine samples remain unchanged. V1 checkpoint status remains `SPLIT_UNVERIFIED`.

Research & Design should decide whether the original Anti-UAV300 partition is a mandatory holdout boundary. If yes, the conservative B ratios must be accepted or a new data-collection policy must be approved; the 70/20/10 target cannot override that boundary.
