# Scope 09 — Results

All six runs processed 301 frames and 272 frames containing detections. Values below are diagnostic counts for this one sequence; they are not independent-test metrics.

| Profile | Gate | Observed GT | Pred-only | Lost | IDs created | ID changes | Non-GT observations | Removed | Alerts | Latency mean / p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| motion | 16 | 255 | 40 | 6 | 7 | 6 | 7 | 6 | 8 | 0.2111 / 0.3725 |
| motion | 25 | 255 | 40 | 6 | 7 | 6 | 7 | 5 | 8 | 0.1708 / 0.2740 |
| motion | 36 | 255 | 40 | 6 | 5 | 4 | 7 | 4 | 6 | 0.1680 / 0.2727 |
| motion_adaptive | 16 | 258 | 38 | 5 | 7 | 6 | 7 | 6 | 8 | 0.1903 / 0.2883 |
| motion_adaptive | 25 | 255 | 31 | 15 | 5 | 4 | 10 | 4 | 6 | 0.1755 / 0.2805 |
| motion_adaptive | 36 | 257 | 35 | 9 | 4 | 3 | 7 | 3 | 6 | 0.1619 / 0.2709 |

All configurations had zero prediction-only alerts and zero duplicate source-frame alerts. GT matching was IoU `>=0.50`; ID changes are consecutive GT-matched tracker-ID changes, not identity-ground-truth changes.

Gate-25 reproducibility: `bytetrack_motion` PASS 301/301 and `bytetrack_motion_adaptive` PASS 301/301 against Scope 08. The machine-readable source of truth is `.runtime/scope09/SCOPE09_RESULTS.json`; per-frame traces are `.runtime/scope09/*_gate*.jsonl`.

Interpretation is intentionally bounded: gate 36 reduces the number of created IDs and ID changes in these replays, but the two profiles do not respond identically, and the same sequence contains fixed-IoU and lifecycle effects. No “best gate” or generalization claim is made. `SPLIT_UNVERIFIED` remains the project status.
