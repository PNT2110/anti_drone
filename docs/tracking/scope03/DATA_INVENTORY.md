# Scope 03 — Data Inventory

## Summary

The repository contains a prepared single-class detector dataset and several
large source archives. The prepared dataset is suitable for detector replay,
but it is not, by itself, an identity-aware MOT ground truth set.

| Item | Result |
|---|---:|
| Prepared manifest entries | 36,732 |
| Prepared sources | `base`: 34,398; `my_dataset`: 2,334 |
| Prepared split counts | train 25,712; val 7,346; test 3,674 |
| Detector class map | class `0` = `drone` |
| Source archives | 6 usable archives plus `.gitkeep` |
| Verified identity annotations in the repo | 0 |
| Continuous sequence prepared by Scope 03 | 1 |

## Source archive inventory

| Archive | Size | Scope 03 finding |
|---|---:|---|
| `data/import_data_rar/Halmstad-Drone.tar` | 665,937,920 B | Contains continuous MP4 files and MATLAB label sidecars; selected source |
| `data/import_data_rar/Drone-vs-Bird.tar` | 4,136,960 B | Available; not selected |
| `data/import_data_rar/my_dataset.tar.xz` | 616,009,768 B | Existing detector source; no temporal identity schema established |
| `data/import_data_rar/UAV-CB.tar` | 6,088,161,280 B | Available; not extracted |
| `data/import_data_rar/DUT-Anti-UAV.tar` | 10,277,939,200 B | Available; not extracted |
| `data/import_data_rar/Anti-UAV300.tar` | 16,778,137,600 B | Available; not extracted |

Only the selected Halmstad video and its label sidecar were extracted. The
large archives were not expanded wholesale and no data was downloaded.

## Prepared detector dataset

The current registry reports a valid 70/20/10 image split with seed 42 and no
image-hash/path/group overlap according to its own audit. A direct group-level
check of `manifest.json` found 318 groups present in more than one split. For
example, `base:RGBT_val_20190925_130434_1_5` has 140 train, 47 validation and
17 test samples. Therefore the registry does not prove sequence-independent
evaluation, and Scope 03 marks the temporal split `SPLIT_UNVERIFIED` without
changing the existing split.

## Relevant artifacts

- `data/processed/drone-single-class/manifest.json`
- `data/processed/drone-single-class/split_registry.json`
- `data/processed/drone-single-class/audit.json`
- `data/tracking_eval/sequence_001/` (ignored local temporal artifact)
- `scripts/prepare_temporal_sequence.py`
- `scripts/validate_tracking_annotations.py`
- `scripts/cache_sequence_detections.py`
