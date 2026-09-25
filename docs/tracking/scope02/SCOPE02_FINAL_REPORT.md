# Scope 02 final report

## Status

`PARTIALLY COMPLETE`

Local artifact validation, ONNX/NCNN host compatibility, fresh parity,
offline integration replay, and same-cache tracker benchmarks are complete.
The required Raspberry Pi 5 environment audit and Pi hardware measurements
remain `BLOCKED — PI HARDWARE ACCESS`.

## 1. Pi OS, Python, architecture

No current Pi access was available. Historical repository evidence records a
Pi aarch64/Python 3.13.5 run, but it is not a Scope 02 audit. The current
execution host is Linux x86_64 with Python 3.14.7.

## 2. Dependency compatibility

Host virtualenv imports passed for OpenCV 5.0.0, ONNX Runtime 1.30.0, and NCNN
1.0.20260526. Pi compatibility remains unverified. `requirements-pi.txt`
expects NumPy `<2.3`, headless OpenCV, ONNX Runtime, and conditional NCNN/
TFLite packages; no system packages or repository constraints were changed.

## 3. ONNX/NCNN checkpoint relationship

Both export metadata records the same source checkpoint SHA256
`662fbc1c066041345970f4211a6ceb9209907a331fd1724c0b2be7e53a4beec1`. Export
file hashes differ as expected. Current artifact paths and hashes are detailed
in `MODEL_ARTIFACT_REPORT.md`.

## 4. Frames processed

The host offline replay processed 8 parity images per profile, for 6 runtime/
profile combinations and 48 end-to-end profile frames total. This is a parity
image set, not a continuous temporal sequence.

## 5. Temporal sequence status

No valid continuous video/temporal sequence was available. The replay is a
smoke/integration validation only. Sequence-boundary reset behavior was added
to the tracking benchmark and covered by regression test.

## 6. Bounding boxes, timestamps, reset

Fresh ONNX and NCNN host replay produced valid in-frame logged boxes, positive
track IDs, monotonic replay timestamps, and explicit observed/predicted state.
The Scope 01 mixed-resolution stale-coordinate defect remains fixed by
frame-shape reset and display/log clipping. No stale alert state was observed.

## 7. Tracker operation on Pi

Not tested. All three profiles ran successfully on the host for both ONNX and
NCNN. This does not establish Pi operation.

## 8. Tracking-only latency

Host-only values are in `PI_TRACKING_BENCHMARK.md`; they must not be used as
Pi estimates. No Pi latency, CPU, RAM, or thermal result exists.

## 9. End-to-end latency

Host ONNX replay means: legacy 26.01 ms, motion 35.29 ms, adaptive 24.61 ms.
Host NCNN replay means: legacy 38.99 ms, motion 40.66 ms, adaptive 53.38 ms.
These include inference, decode/NMS, tracking, alert update, and overlay. They
are not Pi measurements.

## 10. RAM, CPU, temperature

Pi RAM, CPU usage, and temperature are `BLOCKED`. Host short-run peak RSS
values are recorded only as benchmark diagnostics; no thermal or sustained
performance claim is made.

## 11. Fixes and tests

The Scope 02-specific confirmed issue was missing sequence-boundary reset in
the tracking benchmark. The benchmark now resets tracker state and scopes ID
counts at `sequence_id` changes; `tests/test_benchmark.py` covers it. Final
local regression result:

```text
PASS: 18
FAIL: 0
SKIPPED: 0
compileall: PASS
```

## 12. Blocked steps

- Direct Pi environment audit and dependency verification.
- Pi ONNX/NCNN replay.
- Pi tracking-only benchmark with meaningful frame count.
- Pi CPU, RAM, disk, and temperature measurements.
- Continuous temporal-sequence tracking quality validation.
- HOTA/IDF1/IDSW because no identity ground truth exists.

## Evidence

- [PI_ENVIRONMENT_REPORT.md](PI_ENVIRONMENT_REPORT.md)
- [MODEL_ARTIFACT_REPORT.md](MODEL_ARTIFACT_REPORT.md)
- [PI_REPLAY_REPORT.md](PI_REPLAY_REPORT.md)
- [RUNTIME_PARITY_REPORT.md](RUNTIME_PARITY_REPORT.md)
- [PI_TRACKING_BENCHMARK.md](PI_TRACKING_BENCHMARK.md)
- `.runtime/scope02/replay/`
- `.runtime/scope02/detection-cache/`
- `.runtime/scope02/benchmark/`

## Questions for ChatGPT Research & Design

- Can the Pi owner run the supplied commands and provide a fresh aarch64
  environment manifest for the exact exported artifacts?
- What continuous temporal sequence should replace the eight-image parity set
  for meaningful ID retention evaluation?
- After Pi measurements, do ONNX and NCNN remain within the project’s actual
  end-to-end latency and memory budget?
- Which identity ground-truth format should be used for HOTA/IDF1/IDSW without
  changing the tracker architecture?
