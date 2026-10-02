# Scope 11 — Test Report

## Added provenance tests

`tests/test_scope11_provenance.py` covers:

- one-to-many tracking matches remain `POSSIBLE_MATCH`;
- a single exact tracking member can be `CONFIRMED_SOURCE_SEQUENCE`;
- missing archive/source metadata remains `UNRESOLVED`;
- source-group aliases are reported without merging groups;
- `POSSIBLE_MATCH` is never promoted implicitly.

Result: **5 passed**.

The audit command also enforced the 6,505-row accounting invariant and baseline hash/status checks before writing its output. It ran without archive extraction, detector execution, training, tracker changes, or split changes.

## Final verification

- `python -m pytest -q`: **67 passed, 1 skipped**.
- `python -m compileall -q scripts src tests`: **PASS**.
- `git diff --check`: **PASS**.
- V1/V2 baseline hashes after the audit: **unchanged**.
