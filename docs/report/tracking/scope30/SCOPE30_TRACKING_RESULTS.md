# Scope 30 — Tracking Results

No HIGH or LOW detections occurred in the accepted 90-second camera session, so no track ID, target state, loss/reacquisition, or target-center trajectory could be characterized from a real camera-present target. The no-target path recorded 1933 frames and did not fabricate a target.

Software event-injection tests separately cover `HIGH_OBSERVED → PREDICTED → NONE`, low-associated state naming, safe neutral transition, and camera-failure safe state.

## Scope 30R2 / Attempt 3

No detector/tracker frames were collected because the target was absent from the webcam snapshot. Existing software injection evidence remains the source for loss-of-target and camera-failure safety.

## Scope 30R2 / Attempt 4 — live characterization

HIGH detection frames: `7`; LOW-only frames: `212`; track IDs: `[1, 2, 3]`; target observed: `6`; LOW-associated inferred: `4`; prediction-only: `44`; no-target: `1833`; ID changes: `0`; lost/reacquired: `7/4`; target-selection changes: `0`.

LOW association is reported as `LOW_ASSOCIATED_INFERRED` as required.
