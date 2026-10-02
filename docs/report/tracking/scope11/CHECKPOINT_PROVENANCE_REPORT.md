# Scope 11 — Checkpoint Provenance Report

## V1 checkpoint linkage

The inspected model is `yolov8n`; checkpoint SHA-256 is `662fbc1c066041345970f4211a6ceb9209907a331fd1724c0b2be7e53a4beec1`. The training/evaluation provenance points to the V1 manifest SHA-256 `3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d` and V1 split registry SHA-256 `7bc14c2e05b690f2df6c0cfb92e03b565a200f16dd0ef110df8e464837a63a54`.

The checkpoint metadata contains dataset manifest and split hashes, but no archive member, source video, session, or frame key. Therefore the audit can establish only sample-level V1 membership:

| Quarantine rows by V1 split | Count |
|---|---:|
| `train` — confirmed sample-level training input | 5,210 |
| `val` — not a V1 training input sample | 887 |
| `test` — not a V1 training input sample | 408 |

This does not establish source-sequence disjointness. A `val`/`test` row can still be related to a training source sequence when source identity is unavailable. The same limitation applies to any claim about Halmstad independence.

Current status remains **`SPLIT_UNVERIFIED`**. V2 was not activated, no retraining was run, and no source was moved between train/val/test.

Machine-readable evidence: `.runtime/scope11/checkpoint_provenance.json`.
