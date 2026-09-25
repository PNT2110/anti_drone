# Scope 08 — Test Report

## Commands

```text
python scripts/run_scope08_audit.py
python -m pytest -q tests/test_scope08_audit.py
python -m compileall -q scripts src tests
git diff --check
python -m pytest -q
```

## Results

- input audit: `PASS`;
- instrumentation comparison: 301/301 frames `PASS` for all three profiles;
- Scope 08 tests: `8 passed`;
- full regression suite: `44 passed, 1 skipped`;
- skip: `tests/test_runtime.py:4`, optional `cv2` unavailable;
- no tracker algorithm or expected result was modified.

Covered invariants include event/source frame separation, prediction-only
alert suppression, duplicate source-frame suppression, ordered ID-switch
traces, reset ID behavior, instrumentation output equivalence, checksum
mismatch detection, and cache frame-order mismatch detection.

## Artifacts

```text
be9ee2f9a03e3585a808db039815fea9e725cf6fc17ca6347c8253c0f43292b7  .runtime/scope08/input_audit.json
b68e17d911dbda809c43fc8d4a500fc62f88ecf1b0cb38511effc65198b29028  .runtime/scope08/SCOPE08_AUDIT_SUMMARY.json
4025c9fafe867969c8cb2c2378f33a325f7603d3763dfe3f081331aa9f734402  .runtime/scope08/id_switch_events.csv
cee8954ba95c3ef11366fa3f7a38c39f252c5715a45f644e616402ce35081f2b  .runtime/scope08/bytetrack_legacy.jsonl
aae09d4e69a338a67ee0d6cf1ac667ec55866bbc8e4aaf011d58f8efb6483877  .runtime/scope08/bytetrack_motion.jsonl
746e9a149a005c6afbf9230132ef49a4e3efca2bc01904553d9aaa713bfee962  .runtime/scope08/bytetrack_motion_adaptive.jsonl
```
