# Scope 07 — Test Report

## Harness and regression checks

Commands run:

```text
python scripts/run_scope07_diagnostic.py
python -m json.tool .runtime/scope07/SCOPE07_BENCHMARK.json
python -m compileall -q scripts src tests
git diff --check
python -m pytest -q
```

Results:

- input audit: `PASS`;
- three profile replays: `PASS`, 301 JSONL records each;
- JSON benchmark parse: `PASS`;
- repository regression suite: `36 passed, 1 skipped`;
- skip reason: `tests/test_runtime.py:4`, optional `cv2` unavailable;
- no tracker regression test was added because no tracker or data-format bug
  was found and Scope 07 forbids algorithm changes.

The Scope 07 harness itself was smoke-checked against the real 301-record
cache and produced per-frame observed/predicted/lifecycle/alert output for all
three profiles. No HOTA, IDF1, or IDSW tool was run.

## Boundary checks

No YOLO training, detector rerun, dataset split, checkpoint, threshold,
tracker implementation, Pi/camera access, or Git commit/push was performed.
