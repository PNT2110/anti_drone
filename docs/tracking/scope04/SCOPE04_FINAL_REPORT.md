# Scope 04 — Final Report

## Final status

`PARTIALLY COMPLETE — SPLIT UNVERIFIED`

The MATLAB sidecar was successfully parsed and its source boxes were exported.
The selected Halmstad sequence remains unsuitable for independent identity
metrics until split provenance and human identity review are closed.

## Answers to the required questions

1. **Why are 318 groups overlapping?** The group function recognizes RGBT
   video groups, but the split function hashes and assigns individual images;
   it never assigns whole groups.
2. **Is there temporal leakage?** Yes at the prepared-image group level:
   318 groups cross splits and 7,287 nearby same-group/same-modality pairs
   cross splits. Exact duplicate frames were not found.
3. **Does V_DRONE_001 appear in training?** Its exact name occurs zero times in
   the processed manifest. This does not prove source independence because the
   selected archive video is not linked to the detector manifest by durable
   provenance. Status remains `SPLIT_UNVERIFIED`.
4. **What is the MATLAB structure?** MATLAB v5 MCOS opaque `groundTruth` with
   nested `FileWrapper__`, `DataSource`, `LabelDefinitions`, `LabelData` and
   `Version`.
5. **How many original boxes?** 301 DRONE boxes.
6. **How many annotated frames?** 301/301.
7. **Does the sidecar contain identity metadata?** No; zero source track IDs.
8. **Is frame alignment verified?** Yes: 301 rows map to source indices 0–300
   and manifest IDs 1–301; timestamps align at 30 FPS.
9. **How many track IDs are verified?** 0.
10. **Which frames need human review?** All 301 frames are listed as
    `identity_review,PENDING`; no missing, multi-drone or out-of-bounds cases
    were detected.
11. **Tests?** 30 PASS, 0 FAIL, 0 SKIPPED. No HOTA/IDF1/IDSW run.
12. **What is missing for HOTA/IDF1/IDSW?** Human-verified stable `track_id`
    rows and an independent sequence-level split/provenance proof.

## Artifacts

- `docs/tracking/scope04/SPLIT_FORENSIC_REPORT.md`
- `docs/tracking/scope04/MATLAB_SIDECAR_REPORT.md`
- `docs/tracking/scope04/ANNOTATION_ALIGNMENT_REPORT.md`
- `docs/tracking/scope04/IDENTITY_ANNOTATION_REPORT.md`
- `docs/tracking/scope04/SCOPE04_TEST_REPORT.md`
- `data/tracking_eval/sequence_001/matlab_inspection.json`
- `data/tracking_eval/sequence_001/annotations/source_boxes.csv`
- `data/tracking_eval/sequence_001/review/source_boxes_overlay.mp4`
- `data/tracking_eval/sequence_001/review/review_cases.csv`
- `data/tracking_eval/sequence_001/source/V_DRONE_001_LABELS.mat`

## Checksums

```text
9db5a800377c01db8369dfba808d400ca52cd393e0a32850e1d20a4861eaecbe  V_DRONE_001.mp4
39598c0beded8754d5193f57306897dd9302a309c9e391c37ada23eb94646399  V_DRONE_001_LABELS.mat
e4f7a1454e358c30c0e9b257a70c69e92549c5b48bb155ce67d39ea1eed25b1b  frame_manifest.csv
2540e1f42c8e444e5d0077eec1a3a0a82ff34195c428a399cb785c1d2d42c5a9  sequence.json
```

## Reproduction commands

```bash
python scripts/audit_split_leakage.py \
  --manifest data/processed/drone-single-class/manifest.json \
  --output .runtime/scope04_split_audit.json

python scripts/convert_halmstad_sidecar.py \
  --mat data/tracking_eval/sequence_001/source/V_DRONE_001_LABELS.mat \
  --manifest data/tracking_eval/sequence_001/frame_manifest.csv \
  --output data/tracking_eval/sequence_001/annotations/source_boxes.csv \
  --report data/tracking_eval/sequence_001/matlab_inspection.json

python scripts/render_source_review.py \
  --video data/tracking_eval/sequence_001/source/V_DRONE_001.mp4 \
  --boxes data/tracking_eval/sequence_001/annotations/source_boxes.csv \
  --output-dir data/tracking_eval/sequence_001/review \
  --fps 30
```

No source video, source sidecar, dataset split, checkpoint, tracker, Kalman
filter or alert logic was overwritten. No Raspberry Pi access or training was
performed.
