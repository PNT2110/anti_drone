# Scope 27 — Test report

Required detector parity smoke passed: 8/8 images, exact NCNN artifact hashes, class exact, confidence/bbox parity within the existing Scope 20/21 gate.

The offline dry-run passed 301/301 frames with monotonic timestamps, zero coordinate errors, zero timestamp errors, and no frame drops. Existing tracker tests were retained; Scope 27 adds guards for frozen hashes, adapter contract, timestamp/coordinate behavior, dry-run actuator safety, and no autostart.

Commands:

```text
python -m pytest -q
python -m compileall -q scripts src tests
git diff --check
```

No detector, tracker threshold, profile, dataset, TEST result, or production artifact was changed.
