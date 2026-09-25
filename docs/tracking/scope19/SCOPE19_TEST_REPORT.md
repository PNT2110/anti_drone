# Scope 19 — Test report

The final commands and return codes are:

- `PYTHONPATH=. pytest -q` — **PASS**, `96 passed, 1 skipped in 1.04s`.
- `/home/pnt/miniconda3/envs/antidrone/bin/python -m compileall -q scripts src tests` — **PASS**.
- `git diff --check` — **PASS**.
- Six post-export `best.pt` SHA-256 checks — **PASS**, all exact Scope 18 hashes unchanged.

Scope-specific checks cover frozen checkpoint hashes, train-only input manifests, test-lock invariants, declared parity tolerances, output-path safety, and the rule that blocked INT8/TFLite artifacts cannot be reported as exported.
