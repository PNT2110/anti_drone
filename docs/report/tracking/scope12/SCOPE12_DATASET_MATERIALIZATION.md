# Scope 12 — Dataset Materialization

Output: `data/processed/drone-single-class-v2-executable/`.

The 30,227 assigned rows were materialized with physical `shutil.copy2` copies. Symlinks and hardlinks were not used, so downstream training cannot mutate source images through the dataset directory. The build used a temporary sibling directory and atomic rename; the pre-existing V1/V2 trees were not overwritten.

| Split | Images |
|---|---:|
| train | 21,168 |
| val | 6,096 |
| test | 2,963 |
| Total | 30,227 |

Each output row records the V2 row index, source image/label path, source group, split, source image hash, output paths, output image hash, and output label hash in `manifest.json`. `training_provenance.json` records the V2 manifest/registry/audit hashes, seed 42, group/split rules, sample IDs, excluded quarantine counts, validation/test policy, and resume policy.

The materialization did not resize images, edit source images, edit source labels, generate missing labels, or move quarantine samples. The output has its own `data.yaml`, `manifest.json`, `split_registry.json`, `training_provenance.json`, and `materialization_report.json`.
