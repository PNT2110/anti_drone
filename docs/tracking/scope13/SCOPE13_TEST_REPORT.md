# Scope 13 — Test Report

## Scope-specific tests

`tests/test_scope13_provenance.py` covers:

- one source frame mapping to visible and infrared modalities;
- same timestamp with different archive sequence IDs not becoming a shared session;
- ambiguous/missing archive mapping remaining unresolved;
- explicit same-session metadata producing a shared-session status;
- confirmed source collision detection across splits;
- invalid/unresolved filename input not becoming confirmed.

Result: **6 passed**.

## Full verification

- `python -m pytest -q`: **73 passed, 1 skipped**.
- `python -m compileall -q scripts src tests`: **PASS**.
- `git diff --check`: **PASS**.
- Scope 13 resolver: 30,227 mappings, 318 groups, 6 representative decodes, 0 mapping errors.

The existing skipped test is the prior OpenCV-dependent skip. No training, checkpoint replacement, tracker/gate change, Pi/camera access, or Git commit/push occurred.
