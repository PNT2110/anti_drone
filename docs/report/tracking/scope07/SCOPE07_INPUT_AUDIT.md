# Scope 07 — Input Audit

## Result

`PASS — READY FOR SINGLE-SEQUENCE DIAGNOSTIC`

Target: `halmstad_v_drone_001` / `V_DRONE_001`. This is a diagnostic on one
sequence, not an independent test or general benchmark.

| Input | Result |
|---|---:|
| Manifest frames | 301, frame IDs 1–301 |
| Official GT rows | 301, all `track_id=1`, `class_id=0` |
| Identity validation | `PASS`, identity `VERIFIED` |
| Detection cache records | 301, same frame order |
| Cache detection frames | 272/301 |
| Cache/manifest sequence IDs | Match |
| Cache/manifest timestamps | Match within 1e-6 seconds |
| Tracker profiles | Exactly three requested profiles |

The 29 cache frames without detections were retained as-is. No detection was
created, repaired, or dropped by the Scope 07 harness. All three profiles read
the same in-memory cache records in the same order and reset state before
replay.

## Fixed evaluation rule

The GT-to-tracker association rule was declared before replay: maximum bbox
IoU per frame, with `IoU >= 0.50` counted as a GT observation. Predicted boxes
are never counted as detections.

The harness reports tracking-only latency around the tracker update; file I/O,
detector inference, and video decoding are excluded. HOTA, IDF1, and IDSW are
`N/A` in this Scope 07 report because no independently verified MOT-metric
tool/method was invoked; no approximate replacement formula was used.

## Checksums

```text
e4f7a1454e358c30c0e9b257a70c69e92549c5b48bb155ce67d39ea1eed25b1b  data/tracking_eval/sequence_001/frame_manifest.csv
ed76a514237e2e45ed424fc81349b5dbb4e493a1166ecb1116051f3e25abf547  data/tracking_eval/sequence_001/annotations/ground_truth.csv
09168f4bc20b9f357f9af9854f180ca9c2a9fc395311095645a81304f0624f66  data/tracking_eval/sequence_001/detection_cache.onnx.jsonl
bbd4645c04b9bb4540407d8ce61b566d8dad765306ff8348349d9e53382b6c67  data/tracking_eval/sequence_001/review/identity_review_validation.json
b3346cbd71e9851ce23e5320de75570614f40e6d7f45742a1db921c0d275c74f  configs/trackers/bytetrack_legacy.yaml
020fa66d6b3924db8b878da111448eaf2849e904d6f102cdb536fba499f9c358  configs/trackers/bytetrack_motion.yaml
73698ed00c8c28887e5ce90e665added05f4d5496ecebf33da1e74f7a9127eff  configs/trackers/bytetrack_motion_adaptive.yaml
```

## Reproduction

```text
python scripts/run_scope07_diagnostic.py
```

Outputs are written under `.runtime/scope07/`. The cache metadata notes that it
predates Scope 06 and says identity ground truth is pending; this detector-only
metadata was not edited. Scope 07 uses the separately validated official GT.
