# Scope 10 — Temporal Dataset Report

Status: **VALIDATION SET READY — PROVENANCE UNVERIFIED**.

Each selected sequence has:

```text
sequence.json
frame_manifest.csv
source/
annotations/source_boxes.csv
review/identity_status.json
```

Frame manifests use one-based `frame_id`, zero-based `source_frame_index`, source-member references, 30 FPS timestamps, and 640×512 resolution. `ffprobe` frame counting plus an `ffmpeg` decode pass succeeded for all three videos. Source MAT `LabelData` row counts align exactly with decoded frame counts. Source boxes are normalized from `xywh` pixels to `x1,y1,x2,y2`; each selected frame has one DRONE box.

| Sequence | Frame count | Annotation status | Review workload |
|---|---:|---|---|
| `halmstad_v_drone_046` | 312 | source boxes normalized | 312 frames require identity review |
| `halmstad_v_drone_048` | 323 | source boxes normalized | 323 frames require identity review |
| `halmstad_v_drone_045` | 323 | source boxes normalized | 323 frames require identity review |

The dataset-level manifest is [temporal_validation_manifest.json](/run/media/pnt/APP/anti_drone/data/tracking_eval/temporal_validation_manifest.json). It includes the existing reviewed `sequence_001` reference and the three new candidates, with explicit permission rules:

- all four sequences: `diagnostic_only`;
- independent validation: none;
- identity metric ready: none for the three new sequences; sequence 001 is identity-ready in isolation but remains provenance-unverified.

The detector cache step was intentionally not faked. `.runtime/scope10/detector_cache_status.json` is `BLOCKED` because the existing cache script requires OpenCV and this host has no `cv2`; no tracker was run and no detector cache was generated. The current checkpoint hash was still recorded for the future cache run.
