# Scope 14 — Test Report

Scope-specific tests in `tests/test_scope14_policy.py` cover:

- same-prefix videos grouped atomically;
- different prefixes not promoted to session independence;
- original test/val holdout conflict detection;
- candidate-group blocking;
- fixed-seed reproducibility;
- quarantine exclusion;
- no candidate overlap in the audit helper.

Final verification:

- `python -m pytest -q`: **80 passed, 1 skipped**.
- `python -m compileall -q scripts src tests`: **PASS**.
- `git diff --check`: **PASS**.
- Scope 14 dry run: **PASS**, with target-ratio preview explicitly blocked where it violates the conservative source boundary.
- Re-running the same dry run with seed 42 reproduced the conservative CSV and audit JSON byte-for-byte.

No training, production V3 creation, checkpoint change, tracker/gate change, Pi/camera access, or Git commit/push occurred.
