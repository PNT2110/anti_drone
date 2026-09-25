# Scope 23 — Test report

The Scope 23 guard tests cover frozen candidate allowlist, fixed thresholds, TRAIN-only calibration and diagnostics, TEST exclusion, bounded experiment count, and the rule that host parity failure cannot become a production-ready status. The full repository regression commands were run after report generation:

```text
python -m pytest -q        # 113 passed, 1 skipped
python -m compileall -q scripts src tests  # PASS
git diff --check                         # PASS
```

The exact command results are recorded in the final response and the machine-readable runtime summary. No tracker, detector, dataset, split, checkpoint, or TEST artifact was changed.
