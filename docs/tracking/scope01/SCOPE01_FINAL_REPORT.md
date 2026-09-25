# Scope 01 final report

## Status

`PARTIALLY COMPLETE — BLOCKED BY MISSING PI-HARDWARE VALIDATION`

Local OpenCV validation, regression hardening, real-model replay, and
same-detection tracking benchmark are complete. Raspberry Pi live/camera
validation and identity-quality metrics were not run, as required by the
scope restrictions.

## 1. OpenCV validation

Yes. OpenCV-specific tests ran in `/tmp/anti_drone_scope01_venv` using OpenCV
5.0.0.93. The full suite completed with `17 passed`, `0 failed`, and `0
skipped`. NMS xywh conversion and invalid-box handling were executed, not
skipped.

## 2. Confirmed and fixed issues

- The host Python environment lacked `cv2`; a project virtualenv was created
  outside the repository and OpenCV was installed there.
- Mixed-resolution replay carried stale predicted coordinates between image
  coordinate systems. The pipeline now resets on frame-shape change and clips
  overlay/log boxes to the current frame.
- Pipeline/session reset did not previously have one public operation for both
  tracker and alert state. `DetectorPipeline.reset()` now resets tracker IDs,
  alert history, session ID, timestamps, and frame-shape state.
- Regression coverage now explicitly checks two-track/one-detection
  competition and independent per-track alert cooldown.

The pre-existing confirmed issues from the prior implementation—one-pass
legacy association, incorrect NMS coordinate contract, prediction counted as
alert observation, and missing capture timestamp—remain fixed and covered by
the full suite.

## 3. Test counts

```text
PASS: 17
FAIL: 0
SKIPPED: 0
compileall: PASS
```

## 4. End-to-end replay

Yes. The current pipeline processed 8 real repository images through ONNX
inference, decode, NMS, each tracker, temporal alert, overlay, and JSONL
logging. All three profiles completed successfully. The hardened artifacts are
under `.runtime/scope01/replay_hardened/onnx/`.

## 5. Real frames processed

8 frames per profile, 24 profile runs total. The source parity set contains
mixed resolutions; frame-shape reset was exercised and verified.

## 6. Same detection input

Yes for the tracking-only benchmark. YOLO was run once and cached to
`.runtime/scope01/detection-cache/onnx_parity_8frames.jsonl`; all three
profiles consumed that exact eight-record cache. End-to-end replay also used
the same model, input image order, detector threshold, NMS threshold, and
input size for each profile.

## 7. Latency

### End-to-end ONNX replay

| Profile | Mean ms | Max ms |
|---|---:|---:|
| legacy | 31.89 | 35.05 |
| motion | 29.06 | 34.71 |
| motion-adaptive | 24.11 | 28.90 |

### Tracking-only, same detector cache

| Profile | Mean ms | P50 ms | P95 ms | P99 ms |
|---|---:|---:|---:|---:|
| legacy | 0.0171 | 0.0050 | 0.0519 | 0.0534 |
| motion | 0.0911 | 0.0481 | 0.2116 | 0.2287 |
| motion-adaptive | 0.0556 | 0.0302 | 0.1407 | 0.1477 |

These are local x86_64 measurements, not Pi performance claims.

## 8. Identity ground truth

No. HOTA, IDF1, IDSW, fragmentation, false-alert/hour, and time-to-alert are
`N/A`. No quality conclusion is drawn from latency alone.

## 9. Remaining blockers and risks

- No live Pi 5 or USB camera run was performed; this is the main blocker to
  full Scope 01 completion.
- No sustained 1,800-second benchmark was run, per scope prohibition.
- No identity-annotated tracking evaluation is available.
- The temporary validation environment uses host NumPy 2.5.3 because Python
  3.14 had no usable NumPy `<2.3` wheel during setup; dependency parity should
  be rechecked in the project’s supported Pi environment.
- Existing camera evidence includes a prior `BLOCKED` camera-open report; no
  new camera attempt was made.

## 10. Evidence index

- Tests: `SCOPE01_TEST_REPORT.md`
- Replay: `SCOPE01_REPLAY_REPORT.md`
- Benchmark: `SCOPE01_BENCHMARK.md`
- Detection cache: `.runtime/scope01/detection-cache/onnx_parity_8frames.jsonl`
- Tracker benchmark JSON: `.runtime/scope01/benchmark/tracking_profiles.json`
- Hardened replay artifacts: `.runtime/scope01/replay_hardened/onnx/`
- First-run defect evidence: `.runtime/scope01/replay/onnx/`
