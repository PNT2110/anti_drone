# Scope 10 Corrective — Deviation Report

## Missed requirement

The original Scope 10 implementation completed archive inventory, temporal sequence preparation and provenance status, but did not implement the required group-disjoint dataset split V2. It therefore could not claim completion of the corrective objective. Existing V1 was not modified.

## 045 versus 051 discrepancy

The archive listing confirms both paired member sets exist:

```text
Halmstad-Drone/Data/Video_V/V_DRONE_045.mp4
Halmstad-Drone/Data/Video_V/V_DRONE_045_LABELS.mat
Halmstad-Drone/Data/Video_V/V_DRONE_051.mp4
Halmstad-Drone/Data/Video_V/V_DRONE_051_LABELS.mat
```

The current repository was checked directly. `data/tracking_eval/sequence_004/sequence.json`, its frame manifest, and its source directory reference and contain `V_DRONE_045`; no `V_DRONE_051` file is present under `data/tracking_eval/`. The stale sentence in the earlier archive inventory report naming `V_DRONE_051` was corrected to `V_DRONE_045`. No video was renamed, deleted or substituted for this correction.

## Corrective scope

This turn implements only the missing Group-Disjoint Dataset Split V2 and its independent audit. It does not select more videos, create review identity labels, train YOLO, change V1, change the checkpoint, or open Scope 11.
