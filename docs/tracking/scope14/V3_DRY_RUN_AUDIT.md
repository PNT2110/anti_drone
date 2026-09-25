# Scope 14 — V3 Dry-Run Audit

## Option A: current V2

| Metric | Result |
|---|---:|
| Samples | 30,227 |
| Split counts | train 21,168 / val 6,096 / test 2,963 |
| Source sequence overlap | 0 |
| Candidate prefix overlap | 47 prefixes cross splits |
| Source path/hash overlap | 0 |
| Quarantine rows | 0 |
| Session disjointness | `SESSION_DISJOINT_UNVERIFIED` |

## Option B: conservative prefix-atomic with original boundary

| Metric | Result |
|---|---:|
| Candidate groups | 63 |
| Samples | 30,227 |
| Split counts | train 12,142 / val 8,237 / test 9,848 |
| Source sequence overlap | 0 |
| Candidate prefix overlap | 0 |
| Source path/hash overlap | 0 |
| Quarantine rows | 0 |
| Session disjointness | `SESSION_DISJOINT_UNVERIFIED` |

All samples are accounted for exactly once in both dry-run representations. Visible and infrared rows from each source sequence remain together. No source sequence crosses original source splits, so the strict boundary rule produces no blocked candidate group.

## Target-ratio preview (not valid for production)

Using seed 42 and one deterministic greedy assignment over whole prefixes, the target-oriented preview conflicts with the strict original boundary for 43 candidate prefixes / 18,030 samples. Those groups are explicitly `BLOCKED_BY_ORIGINAL_HOLDOUT_BOUNDARY`; they were not silently reassigned.

Evidence:

- `.runtime/scope14/v3_dry_run_a.csv`
- `.runtime/scope14/v3_dry_run_b_conservative.csv`
- `.runtime/scope14/v3_dry_run_b_target_blocked.csv`
- `.runtime/scope14/v3_dry_run_audit.json`
