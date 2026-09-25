# Scope 09 — Event Analysis

The six requested frames were inspected in every replay: 53, 121, 158, 184, 242 and 292. The complete per-frame evidence—including detections, tracker state before/after, association candidates, IoU, Mahalanobis distance, gate result, GT match and lifecycle events—is in `.runtime/scope09/event_analysis.csv` and the six JSONL traces.

The key gate-boundary observations are:

| Frame | Gate-sensitive evidence |
|---:|---|
| 53 | Mahalanobis ≈30.11 for the incumbent. Gate 16 and 25 reject; gate 36 accepts. Gate 16 can show a second candidate because the state differs after the earlier rejection. |
| 121 | Mahalanobis ≈28.53 for the incumbent at the gate-25 replay. Gate 25 rejects; gate 36 accepts. IoU is also below the fixed 0.30 association threshold in the motion profile. |
| 158 | Low-confidence association is accepted at all gates; this frame is not a gate rejection. |
| 184 | Motion profile has IoU 0.0 against the prior predicted box, so the fixed IoU gate rejects; adaptive profile may have no active incumbent after lifecycle handling. This is not evidence that changing Mahalanobis alone fixes the event. |
| 242 | Mahalanobis ≈27.49 at gate 25. Gate 25 rejects and gate 36 accepts for both profiles where the incumbent is active; motion also has a fixed-IoU interaction in some traces. |
| 292 | Motion gate 25 rejects on fixed IoU ≈0.30 boundary; adaptive gate 25 accepts. The event is therefore not purely Mahalanobis-limited. |

Across gates, the main causal pattern is that widening the gate can preserve an incumbent through some large-motion transitions, reducing later ID creation/removal in this sequence. However, the result is profile-dependent and interacts with the fixed IoU gate, lifecycle state, and prediction history. Narrowing the gate can create a new ID sooner; it does not create a “cleaner” identity ground truth.

No prediction-only alert was produced in any configuration, and no duplicate source-frame alert was observed. The alert result is an observed behavior audit, not a threshold optimization.
