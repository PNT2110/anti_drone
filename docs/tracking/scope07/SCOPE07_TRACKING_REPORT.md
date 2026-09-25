# Scope 07 — Tracking Diagnostic Report

## Scope and method

This replay uses only `V_DRONE_001`, 301 frames at 30 FPS, and the same
ONNX detection cache for all profiles. It is not an independent test and does
not establish generalization.

Matching was fixed before replay at maximum bbox IoU `>= 0.50` per frame.
An observed match requires a tracker output with `matched_this_frame=true` and
an observed bbox. A predicted-only frame has no observed GT match but has an
active non-observed track. A lost frame has neither an observed GT match nor an
active predicted track. A false-positive observation is an observed track whose
IoU to the only GT box is below 0.50.

## Per-profile result

| Profile | GT frames | Detection frames | Observed GT | Predicted-only | Lost | Track IDs created | ID changes | FP track IDs | Alerts | Mean tracking-only ms |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| `bytetrack_legacy` | 301 | 272 | 258 | 33 | 10 | 2 | 1 | 2 | 6 | 0.011879 |
| `bytetrack_motion` | 301 | 272 | 255 | 40 | 6 | 7 | 6 | 4, 5 | 8 | 0.145520 |
| `bytetrack_motion_adaptive` | 301 | 272 | 255 | 31 | 15 | 5 | 4 | 3, 4 | 6 | 0.124815 |

`ID changes` means a change in the observed GT-matched track ID between two
matched frames; changes are not treated as proof of physical identity change.
The FP track IDs column lists IDs with at least one observed frame below the
fixed IoU threshold. These are diagnostic signals on this sequence, not a
ranking of general tracking quality.

## Loss and recovery

Frame/timestamp intervals below are the frames where no observed GT match was
available. `recovery` is the next frame with an observed GT match.

| Profile | Predicted-only intervals (frame ranges) | Lost intervals with recovery |
|---|---|---|
| `bytetrack_legacy` | 133–134, 136–150, 159, 162–163, 165–166, 168, 170, 172–178, 181–182 | 151–157 (5.000–5.200s → 158/5.233s); 188 (6.233s → 189/6.267s); 198 (6.567s → 199/6.600s); 200 (6.633s → 201/6.667s) |
| `bytetrack_motion` | 133–134, 136–153, 159, 162–163, 165–166, 168, 170, 172–183, 188 | 154–157 (5.100–5.200s → 158/5.233s); 198 (6.567s → 199/6.600s); 200 (6.633s → 201/6.667s) |
| `bytetrack_motion_adaptive` | 133–134, 136–145, 148, 159, 162–178 | 151–157 (5.000–5.200s → 158/5.233s); 179–183 (5.933–6.067s → 184/6.100s); 188 (6.233s → 189/6.267s); 198 (6.567s → 199/6.600s); 200 (6.633s → 201/6.667s) |

Observed identity changes:

- `bytetrack_legacy`: ID 1 → 2 after the 135–157 gap, resumed at frame 158.
- `bytetrack_motion`: 1 → 2 at 53, 2 → 3 at 121, 3 → 4 at 158, 4 → 5 at
  184, 5 → 6 at 242, and 6 → 7 at 292.
- `bytetrack_motion_adaptive`: 1 → 2 at 53, 2 → 3 at 121, 3 → 4 at 184,
  and 4 → 5 at 242.

## Alert replay

The existing alert policy was replayed without changing thresholds:
3 observations, 2 high-confidence observations, 0.60-second confirmation
window, 2.0-second cooldown, and 0.25 high-confidence threshold.

| Profile | Alert source frames | Prediction-only alerts | Duplicate source-frame alerts |
|---|---|---:|---:|
| `bytetrack_legacy` | 3, 64, 125, 153, 213, 273 | 0 | 0 |
| `bytetrack_motion` | 3, 55, 116, 123, 156, 186, 244, 294 | 0 | 0 |
| `bytetrack_motion_adaptive` | 3, 55, 116, 123, 186, 244 | 0 | 0 |

Every emitted event includes source frame, timestamp, track ID, bbox and
confidence in the per-frame JSONL. Prediction-only tracks did not create an
alert in this replay.

## Latency

Tracking-only latency was measured around `tracker.update()` for 301 frames;
detector, cache parsing, JSONL writing, alert replay, and video I/O are not
included.

| Profile | Mean ms | P50 ms | P95 ms | P99 ms |
|---|---:|---:|---:|---:|
| `bytetrack_legacy` | 0.011879 | 0.012154 | 0.014801 | 0.022199 |
| `bytetrack_motion` | 0.145520 | 0.154380 | 0.236787 | 0.292315 |
| `bytetrack_motion_adaptive` | 0.124815 | 0.121041 | 0.195109 | 0.256496 |

## Artifacts

- `.runtime/scope07/input_audit.json`
- `.runtime/scope07/SCOPE07_BENCHMARK.json`
- `.runtime/scope07/bytetrack_legacy.jsonl`
- `.runtime/scope07/bytetrack_motion.jsonl`
- `.runtime/scope07/bytetrack_motion_adaptive.jsonl`

HOTA, IDF1 and IDSW are `N/A`; no unverified approximation was substituted.
The single-drone sequence cannot test simultaneous-drone identity
competition, cross-target association, or generalization to other videos.

Output checksums:

```text
978038e27668a0bb977a5cbdc4966fae5a34667ba21435510ed76752ac4d8c87  .runtime/scope07/input_audit.json
a564bc44b706c8106db7133666cc1696a21379de466dce0f63fa182e60852c0b  .runtime/scope07/SCOPE07_BENCHMARK.json
8f03e2390250485cd131ac78372aa0cd864b82229e0ea0afc093bedfa1e8e52f  .runtime/scope07/bytetrack_legacy.jsonl
25411fbfd49bf20a0fe7b34859f5242ad65584701f4ec68b790c13e2c8797cc7  .runtime/scope07/bytetrack_motion.jsonl
8802d5d422e06e49a57fb6f1472133f90eadc15e8bf09fdeda0c31c03109d293  .runtime/scope07/bytetrack_motion_adaptive.jsonl
```
