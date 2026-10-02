# Codex implementation report

## 1. Repository state

- Repository: `/run/media/pnt/APP/anti_drone`
- Branch: `main`
- HEAD at inspection: `5996f69 Add repository pipeline and architecture guide`
- Initial working tree: clean and aligned with `origin/main` before this implementation.
- Pre-existing relevant change: the repository guide commit was already present; no checkpoint, dataset, split, model architecture, or systemd/autostart file was modified.
- Current working tree: contains the implementation changes listed below and is intentionally not committed or pushed by this task.

## 2. Verified findings

The following were confirmed by reading the original code, not assumed from the design prompt:

1. `src/anti_drone/runtime.py` used a greedy one-pass `ByteTrackLite` update; it did not perform separate high- and low-confidence association.
2. The original decoder passed restored `xyxy` boxes directly to `cv2.dnn.NMSBoxes`; OpenCV requires `[x, y, width, height]`. The corrected call is now at `runtime.py:79-80`.
3. The original decoder/pipeline defaulted detector confidence to `0.25`, so the requested low-confidence path could be filtered before tracking.
4. The original alert path counted returned tracks without distinguishing a current-frame match from a held/predicted track.
5. The original capture/replay integration passed frame IDs but no capture monotonic timestamp into tracking.

These findings are now covered by regression tests and the legacy adapter remains available for comparison.

## 3. Implemented architecture

```text
LatestFrame (capture timestamp + source frame ID)
  -> DetectorPipeline
  -> preprocess / selected backend
  -> decode + finite-box validation + xyxy-to-xywh NMS
  -> Detection list
  -> ByteTrack high association
  -> ByteTrack low association
  -> Kalman [cx, cy, vx, vy, w, h] using actual dt
  -> TENTATIVE / CONFIRMED / LOST / REMOVED
  -> TemporalAlert on matched observations only
  -> overlay + structured JSONL
```

The motion tracker predicts active tracks before matching. High detections are matched first; only unmatched tracks then see low detections. Low detections never create tracks. New tracks require `new_track_thresh`.

The cost combines IoU, Mahalanobis gating, and—only in the adaptive profile—a normalized center-distance fallback for small objects. Invalid boxes and non-finite confidences are rejected, and accepted pairs are assigned one-to-one deterministically. The legacy profile retains greedy IoU behavior.

Lifecycle timeout is in seconds. A gap beyond `max_gap_before_reset_seconds` clears stale motion state and restarts IDs for a new session. `Track.box` displays the current observation when matched and the Kalman prediction otherwise; `matched_this_frame` and `is_observed` make that distinction explicit.

Temporal alerts maintain per-track histories, require configurable total and high-confidence observations inside a time window, use per-track cooldown, deduplicate source frame IDs, and emit `event_id`, `session_id`, `track_id`, timestamp, bbox, confidence, and observation count.

## 4. Changed files

Created:

- `src/anti_drone/tracking/{__init__,types,association,kalman,lifecycle,bytetrack,bytetrack_legacy}.py` — isolated tracking types, assignment, motion, lifecycle, main tracker, and preserved legacy tracker.
- `src/anti_drone/alerts/{__init__,temporal_alert}.py` — observation-only temporal alerting.
- `configs/trackers/bytetrack_{legacy,motion,motion_adaptive}.yaml` — three reproducible profiles.
- `scripts/benchmark_tracking.py` — JSON/JSONL/CSV tracking-only benchmark.
- `tests/test_tracking.py` and `tests/data/tracking_sample.jsonl` — behavior tests and smoke input.
- `docs/tracking/*.md` — implementation, configuration, testing, benchmark, Pi runbook, and this report.

Modified:

- `src/anti_drone/runtime.py` — decoder/NMS fix, tracker selection, timestamp-aware processing, and structured alert/overlay integration.
- `scripts/run_phase5.py` — capture timestamps, replay source timestamps, CLI tracker/threshold options, and detailed logs.
- `tests/test_runtime.py` — NMS and invalid-box behavior tests; OpenCV guard for hosts without the runtime dependency.
- `pyproject.toml` — pytest source path and test discovery configuration.
- `requirements-dev.txt` — pytest development dependency.

Deleted: none.

## 5. Tests

| Status | Command/result |
|---|---|
| PASS | `python -m pytest -q` — `9 passed, 1 skipped` |
| PASS | `python -m compileall -q src scripts` |
| PASS | `python scripts/benchmark_tracking.py --input tests/data/tracking_sample.jsonl` — all three profiles `DONE` |
| BLOCKED/SKIPPED | OpenCV-specific runtime tests could not execute on this host because `cv2` is not installed; `opencv-python` is declared in `requirements.txt`. |
| NOT RUN | Live Raspberry Pi 5, USB webcam, GPIO, and end-to-end camera acceptance. |

The tests exercise single-track stability, multiple-track one-to-one matching, low-confidence recovery, new-track gating, prediction versus observation, long occlusion, small boxes, dropped timestamps, reconnect reset, duplicate source frames, invalid/empty inputs, determinism, NMS conversion, and the legacy API.

## 6. Benchmark

The tracking-only smoke benchmark used `tests/data/tracking_sample.jsonl` (five synthetic detection records, no identity ground truth) on the local development host. One run reported:

| Tracker | Mean ms | P50 ms | P95 ms | P99 ms | RSS delta KB | Status |
|---|---:|---:|---:|---:|---:|---|
| legacy | 0.026 | 0.022 | 0.048 | 0.050 | 184 | DONE |
| motion | 0.209 | 0.177 | 0.502 | 0.560 | 1144 | DONE |
| motion-adaptive | 0.129 | 0.171 | 0.214 | 0.220 | 0 | DONE |

These are smoke measurements, not stable performance claims. RSS is the
process-level peak delta reported by the host OS and is noisy for such a short
run. HOTA, IDF1, ID switches, fragmentation, false-alert/hour, and time-to-alert
are `N/A`: no identity or alert ground truth was supplied, and no ground truth
was synthesized. No Pi benchmark was claimed.

## 7. Deviations from specification

- A dependency-free exact bitmask assignment is used for small scenes, with a deterministic sorted-pair fallback for unusually large scenes, instead of adding SciPy/Hungarian as a Pi dependency.
- The CLI exposes the three profiles and core parameters directly; YAML files are reference configuration profiles rather than a new YAML runtime loader. This keeps the existing CLI dependency surface unchanged.
- The legacy tracker retains its original frame-count timeout semantics for ablation. Motion profiles use the requested second-based timeout.
- The local host lacks OpenCV, so detector/NMS runtime execution is guarded and marked skipped; it was not misreported as a pass.

## 8. Remaining issues

- Run replay and camera commands on the target Pi with the real exported model and archive their reports.
- Supply an identity-annotated detection stream before making IDF1/HOTA or ID-switch claims.
- Validate the adaptive gate on real small-drone sequences; default values are an initial experiment configuration, not an optimization result.
- Decide in the next research review whether observed latency/ID tradeoffs justify additional OC-SORT research; OC-SORT, BoT-SORT, DeepSORT, ReID, optical flow, and actuator control were intentionally not added.

## 9. Commands

```bash
python -m pytest -q
python -m compileall -q src scripts
python scripts/benchmark_tracking.py --input tests/data/tracking_sample.jsonl --drop-every 4 --output runs/tracking-benchmark.json
```

```bash
python scripts/run_phase5.py replay --runtime onnx --model /path/to/model.onnx --input /path/to/replay-images --output runs/pi5-replay --tracker bytetrack_motion_adaptive --source-fps 30
python scripts/run_phase5.py camera --runtime onnx --model /path/to/model.onnx --output runs/pi5-camera --device /dev/video0 --tracker bytetrack_motion_adaptive --duration-seconds 30
python scripts/run_phase5.py replay --runtime onnx --model /path/to/model.onnx --input /path/to/replay-images --output runs/pi5-legacy --tracker bytetrack_legacy
```

## 10. Questions for Research & Design

- On annotated sequences, does adaptive center-distance gating reduce ID switches for small drones without increasing false associations?
- Which profile gives the best HOTA/IDF1 and fragmentation tradeoff at the target Pi frame rate?
- Does the motion Kalman path remain within the acceptable end-to-end latency budget after real inference is included?
- Should alert confirmation and cooldown be tuned from measured false-alert/hour and time-to-alert data?
- Is OC-SORT worth a follow-up ablation after these three baselines are scored?
