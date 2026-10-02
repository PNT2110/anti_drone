# Scope 08 — Input Audit

## Result

`PASS`

The audit used only `halmstad_v_drone_001` / `V_DRONE_001`, the Scope 06
human-verified GT, the existing detector cache, the three Scope 07 JSONL
outputs, and the existing tracker YAML files. Scope 07 outputs were read but
not overwritten.

| Check | Result |
|---|---:|
| Manifest | 301 ordered frames |
| Official GT | 301 rows, physical ID 1 |
| Identity validator | `PASS`, `VERIFIED` |
| Detection cache | 301 ordered records, 272 frames with detection |
| Profile outputs | 301 rows per profile |
| Trace windows | 50–55, 118–124, 130–160, 180–187, 239–246, 289–295 |
| Fixed GT matching | IoU `>= 0.50` |
| Instrumentation comparison | 301/301 frames `PASS` for all profiles |

No detection, GT, tracker configuration, or Scope 07 artifact was changed.

## Reproduction

```text
python scripts/run_scope08_audit.py
```

The command writes only `.runtime/scope08/`. A checksum or frame-order
mismatch causes `BLOCKED` and stops the replay.

## Input checksums

```text
e4f7a1454e358c30c0e9b257a70c69e92549c5b48bb155ce67d39ea1eed25b1b  frame_manifest.csv
ed76a514237e2e45ed424fc81349b5dbb4e493a1166ecb1116051f3e25abf547  ground_truth.csv
09168f4bc20b9f357f9af9854f180ca9c2a9fc395311095645a81304f0624f66  detection_cache.onnx.jsonl
bbd4645c04b9bb4540407d8ce61b566d8dad765306ff8348349d9e53382b6c67  identity_review_validation.json
b3346cbd71e9851ce23e5320de75570614f40e6d7f45742a1db921c0d275c74f  bytetrack_legacy.yaml
020fa66d6b3924db8b878da111448eaf2849e904d6f102cdb536fba499f9c358  bytetrack_motion.yaml
73698ed00c8c28887e5ce90e665added05f4d5496ecebf33da1e74f7a9127eff  bytetrack_motion_adaptive.yaml
```

Scope 07 replay-output checksums recorded by the audit:

```text
8f03e2390250485cd131ac78372aa0cd864b82229e0ea0afc093bedfa1e8e52f  .runtime/scope07/bytetrack_legacy.jsonl
25411fbfd49bf20a0fe7b34859f5242ad65584701f4ec68b790c13e2c8797cc7  .runtime/scope07/bytetrack_motion.jsonl
8802d5d422e06e49a57fb6f1472133f90eadc15e8bf09fdeda0c31c03109d293  .runtime/scope07/bytetrack_motion_adaptive.jsonl
```

The machine-readable audit and exact path-to-checksum mapping are in
`.runtime/scope08/input_audit.json`.
