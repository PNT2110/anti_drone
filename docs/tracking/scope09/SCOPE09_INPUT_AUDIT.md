# Scope 09 — Input Audit

Status: **PASS** (offline single-sequence diagnostic only).

The replay used the fixed Halmstad sequence `halmstad_v_drone_001`, 301 frames, the user-verified ground truth ID 1, and the existing detection cache. The identity-review validation was `PASS`; the cache, manifest, GT, timestamps and sequence IDs were checked before replay. Detection input was not regenerated or edited.

Fixed input checksums (SHA-256):

| Input | SHA-256 |
|---|---|
| `data/tracking_eval/sequence_001/frame_manifest.csv` | `e4f7a1454e358c30c0e9b257a70c69e92549c5b48bb155ce67d39ea1eed25b1b` |
| `data/tracking_eval/sequence_001/annotations/ground_truth.csv` | `ed76a514237e2e45ed424fc81349b5dbb4e493a1166ecb1116051f3e25abf547` |
| `data/tracking_eval/sequence_001/detection_cache.onnx.jsonl` | `09168f4bc20b9f357f9af9854f180ca9c2a9fc395311095645a81304f0624f66` |
| `data/tracking_eval/sequence_001/review/identity_review_validation.json` | `bbd4645c04b9bb4540407d8ce61b566d8dad765306ff8348349d9e53382b6c67` |

Scope 08 baseline artifacts were also verified against their recorded hashes before this study. The two production YAML files were unchanged. `SPLIT_UNVERIFIED` remains unchanged.

The declared gate values were fixed before replay: `16.0`, `25.0`, `36.0`. Only `adaptive_mahalanobis_gate` was overridden in an in-memory `ByteTrackConfig`; the detector, cache, thresholds, Kalman noise, lifecycle, alert configuration, timestamps and reset behavior were held fixed.

Reproduction command:

```bash
python scripts/run_scope09_gate_sensitivity.py
```

Machine-readable audit: `.runtime/scope09/input_audit.json`.
