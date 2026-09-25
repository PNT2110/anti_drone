# Scope 06 — Test Report

## Result

```text
36 passed, 1 skipped
```

The skipped test is `tests/test_runtime.py:4`, skipped because the current
environment does not provide the optional `cv2` module. It is an environment
limitation, not a failed Scope 06 assertion.

## Scope 06 coverage

`tests/test_identity_review.py` now covers:

- pending preparation and export blocking;
- complete batch evidence and evidence SHA provenance;
- overlapping segments;
- out-of-range segments;
- invalid assigned track IDs;
- missing reviewer evidence fields;
- partial batch review without official export;
- `NEEDS_REVIEW` evidence remaining non-official.

Additional checks completed:

- `python -m compileall -q scripts src tests` — PASS;
- `git diff --check` — PASS;
- overlay decode count — 301 frames;
- source-box/manifest row count — 301/301.
- identity validator with `--export-ground-truth` — `PASS`;
- ground-truth integrity — 301 rows, unique frames 1–301, all ID 1/class 0,
  301/301 source-box matches, valid coordinates.

No tracker, model, split, checkpoint, Raspberry Pi runtime, HOTA, IDF1, or
IDSW evaluation was changed or run.
