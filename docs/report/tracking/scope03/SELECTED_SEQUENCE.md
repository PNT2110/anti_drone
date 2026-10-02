# Scope 03 — Selected Sequence

## Selection

`halmstad_v_drone_001` was selected because the source archive contains the
original continuous video rather than only sparsely sampled detector frames.

| Field | Value |
|---|---|
| Archive | `data/import_data_rar/Halmstad-Drone.tar` |
| Video member | `Halmstad-Drone/Data/Video_V/V_DRONE_001.mp4` |
| Label sidecar | `Halmstad-Drone/Data/Video_V/V_DRONE_001_LABELS.mat` |
| Modality | Visible video (`V`) |
| Frame count | 301 reported / 301 decoded |
| Duration | 10.033 s by frame count at 30 FPS |
| FPS | 30.0, read from the source video container |
| Resolution | 640 × 512 |
| Timestamp formula | `source_frame_index / 30.0` seconds |
| Temporal continuity | Frame indices 0–300; no decode gap found |
| Split status | `SPLIT_UNVERIFIED` |
| Identity GT status | `DATA READY — IDENTITY ANNOTATION PENDING` |

## Local artifact

The sequence is materialized under the ignored path
`data/tracking_eval/sequence_001/`:

- `sequence.json` — source and decode metadata;
- `frame_manifest.csv` — 301 ordered frames and timestamps;
- `source/V_DRONE_001.mp4` — only the selected video member;
- `source/V_DRONE_001_LABELS.mat` — original sidecar retained unchanged;
- `annotations/ground_truth.csv` — schema-only file, intentionally empty;
- `validation_report.json` — validator result;
- `detection_cache.onnx.jsonl` — detector-only cache for 301 frames.

The MATLAB sidecar contains a `gTruth` object, but it has not been normalized
into verified row-level identity annotations. Scope 03 does not infer IDs from
detector outputs or manufacture pseudo ground truth.

## Reproduction

```bash
python scripts/prepare_temporal_sequence.py \
  --archive data/import_data_rar/Halmstad-Drone.tar \
  --video-member Halmstad-Drone/Data/Video_V/V_DRONE_001.mp4 \
  --labels-member Halmstad-Drone/Data/Video_V/V_DRONE_001_LABELS.mat \
  --output data/tracking_eval/sequence_001 \
  --sequence-id halmstad_v_drone_001
```

The command extracts only two named archive members and checks that the
container frame count equals the decoded frame count.
