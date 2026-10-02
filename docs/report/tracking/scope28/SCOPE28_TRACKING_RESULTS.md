# Scope 28 — Tracking Results

| Metric | Value |
|---|---|
| Frames processed | 301 |
| Track IDs created | [1, 2, 3, 4, 5] |
| Target observed frames | 217 |
| Prediction-only frames | 31 |
| No-target frames | 53 |
| ID changes | 2 |
| Lost events | 11 |
| Reacquisition events | 10 |
| Coordinate errors | 0 |
| Timestamp errors | 0 |

Scope 27 baseline for comparison was observed=204, predicted-only=41, no-target=56, IDs=[1,2,3,4,5], ID changes=2, lost=17, reacquisition=16. Scope 28 characterization is not an optimization or a claim of generalization; differences reflect the restored low-score observation input.

Per-frame high/low detections, track IDs, state, association-source inference, and dry-run command preview are in `.runtime/scope28/target_state.jsonl`.
