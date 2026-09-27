# Scope 28 — Test Report

Accepted Pi evidence: fixed 8-image parity PASS; Halmstad 301/301 dual-stream dry-run PASS; high-stream equivalence 301/301 PASS; coordinate and timestamp errors 0; actuator writes 0.

Regression suite after implementation: **135 passed, 1 skipped**. `python -m compileall -q scripts src tests` passed. `git diff --check` passed.

The first transport attempt exposed a harness key lookup error while reading the frozen host reference. It was corrected before the accepted run; it was not a model, tracker, threshold, or artifact change.
