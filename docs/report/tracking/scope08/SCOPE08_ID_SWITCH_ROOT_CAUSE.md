# Scope 08 — ID-Switch Root-Cause Audit

## Evidence policy

The audit does not infer a cause from aggregate counts. It records detector
classification, association candidates and gate reasons, track lifecycle
events, GT IoU, and the frame where a new ID was first created. Labels below
refer to the Scope 08 categories:

- `C`: tracker association failed;
- `D`: previous track was removed or no longer active by lifecycle;
- `E`: the reported switch became visible only when GT IoU crossed 0.50;
- `UNKNOWN`: insufficient evidence.

## Verified events

| Profile | Reported switch | Trace result | Evidence |
|---|---:|---|---|
| legacy | 158: 1 → 2 | `E + C + D` | ID 2 created at 151; frame 151 association to ID 1 had IoU 0.035 `< 0.30`; ID 1 was removed after lifecycle timeout; ID 2 was observed at frames 151–158, but GT IoU first reached 0.530 at frame 158. |
| motion | 53: 1 → 2 | `C` | Detection confidence 0.712; IoU 0.387, Mahalanobis 30.110 `>25`; high-stage gate rejected ID 1; ID 2 created. |
| motion | 121: 2 → 3 | `C` | Detection confidence 0.506; IoU 0.261 `<0.30`, Mahalanobis 28.526 `>25`; high-stage gate rejected ID 2; ID 3 created. |
| motion | 158: 3 → 4 | `E + C + D` | ID 4 created at 154; previous ID 3 association had IoU 0.023 and Mahalanobis 52.130, then lifecycle removed ID 3; GT IoU for ID 4 reached 0.530 at frame 158. |
| motion | 184: 4 → 5 | `C` | Detection confidence 0.535; previous ID 4 was still `LOST`; high-stage IoU was 0.000 `<0.30`; ID 5 created. |
| motion | 242: 5 → 6 | `C` | Detection confidence 0.731; GT IoU 0.775, but association IoU 0.328 and Mahalanobis 27.485 `>25`; ID 6 created. |
| motion | 292: 6 → 7 | `C` | Detection confidence 0.675; GT IoU 0.807, but association IoU was approximately 0.300 and rejected as below the fixed 0.30 tracker gate; ID 7 created. |
| adaptive | 53: 1 → 2 | `C` | Same cached detection; Mahalanobis 30.110 `>25` rejected the adaptive association. |
| adaptive | 121: 2 → 3 | `C` | Same cached detection; Mahalanobis 28.526 `>25` rejected the adaptive association. |
| adaptive | 184: 3 → 4 | `D` | ID 3 was removed at frame 179 by lifecycle timeout after remaining lost; frame 184 had no active track to associate, so high detection created ID 4. |
| adaptive | 242: 4 → 5 | `C` | Same cached detection as motion; Mahalanobis 27.485 `>25` rejected ID 4. |

The full per-frame evidence is in the three Scope 08 JSONL traces and
`id_switch_events.csv`. No event is attributed to detector absence when the
cache contained a detection.

## Requested windows

The traces include all requested windows: 50–55, 118–124, 130–160, 180–187,
239–246, and 289–295. For each frame they retain detector bbox/confidence and
classification, association stage and scores, track state, observed/predicted
status, lifecycle changes, GT IoU, and GT-matched ID.

## Unverified hypotheses

This audit does not establish that a different Kalman model, threshold, or
association strategy would improve retention. It also does not establish
generalization beyond this single drone sequence. Those are Research & Design
questions for a later, explicitly authorized scope.
