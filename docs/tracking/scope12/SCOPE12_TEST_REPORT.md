# Scope 12 — Test Report

## Executed checks

| Check | Result |
|---|---|
| `python scripts/materialize_scope12_dataset.py` | PASS — 30,227 copies |
| `python scripts/audit_scope12_source_provenance.py` | PASS — 30,227 path/hash matches; archive keys unresolved as reported |
| `python scripts/audit_scope12_executable_dataset.py` | PASS |
| `antidrone/bin/python scripts/scope12_loader_smoke.py` | PASS — Ultralytics loader read train/val/test; three exact weights loaded |
| `python -m pytest -q` | 67 passed, 1 skipped |
| `python -m compileall -q scripts src tests` | PASS |
| `git diff --check` | PASS |

The one skipped regression test is the existing OpenCV-dependent skip from prior scopes. No training epoch was run, no checkpoint was changed, and no Pi/camera/tracker/gate action was performed.

Loader smoke evidence is `.runtime/scope12/loader_smoke.json`; direct dataset audit evidence is `data/processed/drone-single-class-v2-executable/executable_dataset_audit.json`.
