# Scope 10 Corrective — Group Contract Report

## Implementation audit

`scripts/prepare_dataset.py` defines `group_for()` as follows:

- `base:RGBT_*`: removes modality and trailing frame token, so visible and infrared rows from the same encoded RGBT sequence share one group;
- `base:DUT_*`: keeps each image stem as a separate group because the prepared filename has no reliable sequence key;
- `my_dataset`: all rows share `my_dataset`;
- other fallback names: source plus stem.

The same script's `assign_splits()` does not consume these groups. It forces `my_dataset` into train, then sorts individual remaining samples by a seed/hash key and slices the sample list into train/val/test. This explains the Scope 04 finding of 318 RGBT groups crossing splits.

## V2 contract

| Classification | Rule | Count | V2 policy |
|---|---|---:|---|
| `VERIFIED_SEQUENCE_GROUP` | `source=base` and `group` starts `base:RGBT_` | 318 groups / 30,227 samples | assign whole group to one split |
| `VERIFIED_INDEPENDENT_IMAGE` | explicit independent-source metadata | 0 | none inferred |
| `GROUP_UNVERIFIED` | `my_dataset`, DUT/fallback groups, or missing sequence provenance | 4,172 groups / 6,505 samples | quarantine |

The RGBT grouping is a source-sequence contract based on the explicit filename fields already used by the repository. It does not prove independence from the frozen checkpoint; that is a separate training-provenance question. Filename absence is never promoted to independent-image status.

All 36,732 source rows are represented in V2 with exactly one `ASSIGNED` or `QUARANTINED` status. No source image is copied, moved or edited.
