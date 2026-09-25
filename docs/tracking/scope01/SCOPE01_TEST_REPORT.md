# Scope 01 test report

## Environment

Tests were run in the temporary project virtualenv:

```text
Interpreter: /tmp/anti_drone_scope01_venv/bin/python
Python: 3.14.7
OpenCV: 5.0.0.93
NumPy: 2.5.3 (provided by the host Miniconda site-packages)
pytest: 9.1.1
ONNX Runtime: 1.30.0
```

The first isolated attempt tried to build a NumPy wheel for Python 3.14 and
was cancelled because this repository constraint did not have a compatible
wheel in that environment. A second virtualenv used the existing NumPy site
package and installed OpenCV/ONNX Runtime inside the virtualenv only; no
system Python package was modified.

## Results

```text
/tmp/anti_drone_scope01_venv/bin/python -m pytest -q
17 passed in 0.11s

/tmp/anti_drone_scope01_venv/bin/python -m compileall -q src scripts
PASS
```

There were no skipped tests in the Scope 01 virtualenv. The earlier host
interpreter still lacks `cv2`, but it is not the environment used for this
Scope 01 acceptance run.

## Covered behavior

- OpenCV NMS receives xywh boxes and suppresses/returns valid detections.
- Zero-area, non-finite, and empty decoder inputs are rejected safely.
- High then low association, new-track threshold, and low-confidence no-new
  track behavior.
- Deterministic one-to-one matching, including two tracks competing for one
  detection.
- Actual timestamp delta, prediction, dropped-frame gaps, lifecycle timeout,
  and long-gap reset.
- Small-object adaptive association versus fixed-IoU motion association.
- Observation-only alerting, duplicate source-frame suppression, per-track
  cooldown, and prediction exclusion.
- Pipeline/session reset clears tracker IDs, alert history, and session ID.
- Legacy tracker positional API remains usable.

## Status

`PASS` for local regression and OpenCV-specific validation. Live Pi and camera
checks are intentionally not part of this local result.
