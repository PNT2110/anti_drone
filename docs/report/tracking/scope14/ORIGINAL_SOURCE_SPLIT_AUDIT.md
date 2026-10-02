# Scope 14 — Original Anti-UAV300 Source Split Audit

## Evidence

The RGBT archive path has an explicit source partition:

```text
Anti-UAV300/data/Anti-UAV300/{train|val|test}/{date}_{time}_{stream}_{sequence}/...
```

The archive also contains `label_new/train.json`, `label_new/val.json`, and `label_new/test.json`. Their sequence membership agrees exactly with the path partition for all 318 mapped sequences:

| Original source split | Source sequence directories | Samples |
|---|---:|---:|
| train | 160 | 12,142 |
| val | 67 | 8,237 |
| test | 91 | 9,848 |
| Total | 318 | 30,227 |

This is strong evidence of an official dataset partition. It is not, by itself, proof that the three partitions are statistically independent sessions or that the archive's `test` partition is an approved external holdout for this project. No explicit session-ID rule or independence guarantee was found in the inspected archive metadata/code.

## Original source split × current V2 split

| Original source split | V2 train | V2 val | V2 test | Total |
|---|---:|---:|---:|---:|
| train | 8,603 | 2,356 | 1,183 | 12,142 |
| val | 5,655 | 1,762 | 820 | 8,237 |
| test | 6,910 | 1,978 | 960 | 9,848 |
| Total | 21,168 | 6,096 | 2,963 | 30,227 |

The current V2 sequence assignment preserves each mapped source sequence, but it does not preserve the original source partition. If original `test`/`val` are treated as protected holdouts, 6,910 original-test samples and 5,655 original-val samples are currently in V2 train. This is reported as risk, not as a proven model leakage claim.

No source prefix crosses original source partitions: each of the 63 date/time prefixes belongs to one original source partition. The full machine-readable matrix is `.runtime/scope14/original_source_split_matrix.csv`.
