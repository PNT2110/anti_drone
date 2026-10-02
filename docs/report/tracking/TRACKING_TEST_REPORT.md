# Tracking test report

## Automated checks

Run from the repository root:

```bash
python -m pytest -q
python -m compileall -q src scripts
```

The implemented tests cover:

- high/low two-stage association and the new-track confidence threshold;
- deterministic one-to-one matching;
- timestamp-derived prediction and dropped-frame gaps;
- adaptive small-object association versus fixed-IoU motion association;
- second-based lifecycle timeout and long-gap session reset;
- observation-only alerts, prediction exclusion, source-frame deduplication,
  and cooldown-ready history;
- backward timestamps, empty/invalid detections, explicit reset, and the
  original legacy positional API.

In the development environment used for this implementation, the result was
`9 passed, 1 skipped`. The skipped legacy detector test is guarded because
OpenCV (`cv2`) is not installed in that environment; the declared runtime
requirements include `opencv-python`, and the test runs when that dependency
is installed.

## Hardware boundary

No USB webcam, Raspberry Pi 5, GPIO, or live camera acceptance test was run in
this environment. Those checks remain a Pi-side step in the runbook. The
tracking-only benchmark intentionally does not claim detector or camera FPS.
