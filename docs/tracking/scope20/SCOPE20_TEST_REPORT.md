# Scope 20 — Test report

Final commands and results:

- `PYTHONPATH=. python -m pytest -q` — **PASS**, `103 passed, 1 skipped in 1.06s`.
- `/home/pnt/miniconda3/envs/antidrone/bin/python -m compileall -q scripts src tests` — **PASS**.
- `git diff --check` — **PASS**.
- Final baseline audit — **PASS**, 6 checkpoint hashes and 12 Scope 19 export hashes unchanged.

Scope-specific regression checks cover preprocessing color/order and `rect=False`, letterbox static-size policy, output transpose and YOLO26 contract, one-NMS-only behavior, confidence/IoU invariants, exact locked image membership, train-only calibration, Pi identity blocking, checkpoint immutability, and the rule that parity-fail backends cannot become READY.
