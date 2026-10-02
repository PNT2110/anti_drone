# Scope 10 Corrective — Split V2 Independent Audit

Independent audit status: **PASS**. The audit reads the V2 output and source V1 manifest independently; it does not trust the V2 registry's overlap field.

| Check | Result |
|---|---:|
| Source samples accounted for | 36,732 / 36,732 |
| V2 duplicate/lost/extra samples | 0 |
| Verified groups | 318 |
| Verified group overlap across train/val/test | 0 |
| Exact source-path overlap | 0 |
| Exact image-hash overlap | 0 |
| GROUP_UNVERIFIED samples | 6,505 |
| GROUP_UNVERIFIED groups | 4,172 |
| Independent-validation claim | false |

Actual assigned split counts and ratios:

| Split | Samples | Ratio over assigned 30,227 |
|---|---:|---:|
| train | 21,168 | 70.0301% |
| val | 6,096 | 20.1674% |
| test | 2,963 | 9.8025% |
| quarantine | 6,505 | not included in assigned ratio |

The ratio is approximate because group boundaries are preserved. Visible/infrared rows from each verified RGBT sequence share the same group and split. The audit reports provenance uncertainty separately instead of calling V2 fully source-disjoint.

Reproduction:

```bash
python scripts/build_group_disjoint_split_v2.py --seed 42
python scripts/audit_group_disjoint_split_v2.py
```

The same source manifest, seed and algorithm produced identical V2 manifest and registry hashes in a separate temporary rebuild.
