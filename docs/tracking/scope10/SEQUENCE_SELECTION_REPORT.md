# Scope 10 — Sequence Selection Report

Selection was made after archive inventory and before any tracker replay. The fixed rule was: choose at most three continuous visible Halmstad `V_DRONE_*` members with matching MAT sidecars, prioritizing the largest available video members as a reproducible duration proxy. No tracker result, detector output or gate result was used for selection.

| Sequence | Source member | Frames | FPS | Resolution | Source boxes | Multiple boxes | Identity | Provenance | Permission |
|---|---|---:|---:|---|---:|---:|---|---|---|
| `halmstad_v_drone_046` | `V_DRONE_046.mp4` + `V_DRONE_046_LABELS.mat` | 312 | 30 | 640×512 | 312 | 0 | IDENTITY REVIEW REQUIRED | PROVENANCE_UNVERIFIED | diagnostic_only |
| `halmstad_v_drone_048` | `V_DRONE_048.mp4` + `V_DRONE_048_LABELS.mat` | 323 | 30 | 640×512 | 323 | 0 | IDENTITY REVIEW REQUIRED | PROVENANCE_UNVERIFIED | diagnostic_only |
| `halmstad_v_drone_045` | `V_DRONE_045.mp4` + `V_DRONE_045_LABELS.mat` | 323 | 30 | 640×512 | 323 | 0 | IDENTITY REVIEW REQUIRED | PROVENANCE_UNVERIFIED | diagnostic_only |

The existing `halmstad_v_drone_001` (301 frames) is retained in the manifest as a reference diagnostic sequence: its identity is user-verified, but source/training disjointness remains unverified. It is not counted as one of the three newly selected candidates.

No selected sequence has source-proven identity IDs. The MAT sidecars contain class rectangles and time fields, not stable track IDs. Scope 10 creates review status and workload only; it does not assign identity IDs or export new identity ground truth.
