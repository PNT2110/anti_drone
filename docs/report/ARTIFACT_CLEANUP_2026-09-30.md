# Artifact cleanup — 2026-09-30

## Dataset verification before cleanup

- Canonical dataset: `data/data_train`.
- Images: 110,469.
- Labels: 110,469.
- Missing labels: 0.
- Orphan labels: 0.

## Removed legacy or temporary groups

- `artifacts/benchmarks/`
- `artifacts/experiments/`
- `artifacts/exports/`
- `artifacts/integration/`
- `artifacts/maintenance/`
- `artifacts/transfer_cache/`

These groups contained historical experiments, temporary transfer copies, and
superseded export/evaluation files. The source archives remain under
`data/import_data_rar/` and the validated dataset remains under `data/data_train/`.

## Preserved deployment groups

- `artifacts/deploy/`
- `artifacts/deploy-320/`
- `artifacts/production-candidate/`
- `artifacts/releases/`
- `artifacts/models/`

These are kept for the web detector and Pi 5 deployment.
