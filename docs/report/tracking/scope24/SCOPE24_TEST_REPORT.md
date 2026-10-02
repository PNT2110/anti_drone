# Scope 24 — Test report

Regression guards cover the two-model allowlist, immutable baseline hashes, exact image sizes, TRAIN-only calibration, TEST exclusion, fixed confidence/NMS thresholds, T1/T2 bound, ORT one-variant bound, host-fail transfer prohibition, Pi identity requirement, and no NCNN E4+ experiments.

Commands:

```text
python -m pytest -q
python -m compileall -q scripts src tests
git diff --check
```

No dataset, label, split, tracker, checkpoint, TEST artifact, production detector, or Git history was changed.
