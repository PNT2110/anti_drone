# Data train import report — 2026-09-30

## Final verified result

- Canonical directory: `data/data_train/`.
- Total images: **110,469**.
- Total YOLO labels: **110,469**.
- Missing labels: **0**.
- Orphan labels: **0**.

## Newly imported sources

| Source | Accepted | Train | Validation | Test | Rejected/deduplicated |
|---|---:|---:|---:|---:|---:|
| DUT-Anti-UAV | 9,453 | 5,194 | 2,599 | 1,660 | 3 invalid labels, 546 duplicate images |
| UAV-CB | 6,784 | 5,593 | 1,191 | 0 | 2 missing/invalid samples |
| **Total** | **16,237** | **10,787** | **3,790** | **1,660** | — |

The source archives were extracted to `data/import_extracted/` for auditability.
The original archives remain under `data/import_data_rar/`; `my_dataset.tar.xz`
was not modified or included in the cleanup.

## Training note

The server training job is intentionally stopped. The next run should train from
the base/pretrained weights against this verified 110,469-image dataset, rather
than resume the previous 94,232-image run.
