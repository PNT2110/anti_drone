# Scope 22 — Test report

Host checks after implementation:

- `PYTHONPATH=. python -m pytest -q` — **PASS**, `109 passed, 1 skipped in 1.02s`.
- `python -m compileall -q scripts src tests` — **PASS**.
- `git diff --check` — **PASS**.

Scope-specific guards cover the three-candidate allowlist, YOLO26 NCNN exclusion, exact train-only calibration membership, TEST prohibition, immutable Scope 20 hashes, INT8 readiness requiring quantization evidence, and FP32/INT8 schema equivalence. No TEST inference, camera, tracker, servo, retraining, split change, or production freeze occurred.
