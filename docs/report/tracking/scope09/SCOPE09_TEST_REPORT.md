# Scope 09 — Test Report

The Scope 09 regression coverage verifies:

- default `ByteTrackConfig` remains at Mahalanobis gate 25.0;
- an experiment override changes only that field;
- tracker state resets between runs;
- the source cache is read-only and remains checksum-identical;
- prediction-only input cannot create an alert observation;
- both gate-25 replays reproduce Scope 08 frame-by-frame;
- all six declared profile/gate combinations are present and preserve alert invariants.

Commands:

```bash
python -m pytest -q tests/test_scope09_gate_sensitivity.py
python -m pytest -q
python -m compileall -q scripts src tests
git diff --check
```

Final result: **50 passed, 1 skipped**. The skipped test is the existing `tests/test_runtime.py` OpenCV-dependent test when `cv2` is unavailable; this is not a Scope 09 failure. `compileall` and `git diff --check` also passed.
