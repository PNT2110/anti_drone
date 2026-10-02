# Scope 04 — Split Forensic Report

## Status

`CONFIRMED TEMPORAL LEAKAGE` at the prepared-image sequence-group level.

This is not an exact duplicate-frame finding. It is a split-independence
failure: images identified as samples from the same RGBT video group were
assigned to train, validation and test independently.

## Root cause

`scripts/prepare_dataset.py` defines an RGBT group by removing the modality and
trailing frame token from a filename:

```text
RGBT_<date>_<time>_<camera>_<sequence>_<modality>_<frame>.jpg
→ base:RGBT_<date>_<time>_<camera>_<sequence>
```

The same function intentionally keeps visible and infrared samples in one
group. However, `assign_splits()` sorts individual samples by an image-hash
key and fills train/val/test quotas; it never groups samples before assigning
the split. The registry's `\"overlap\": {\"group\": 0}` is therefore an audit
placeholder, not evidence of group-disjoint assignment.

## Evidence

| Check | Result |
|---|---:|
| Samples | 36,732 |
| Groups | 4,490 |
| Groups in more than one split | 318 |
| Rows belonging to those groups | 30,227 |
| Exact `(group, modality, source-frame)` across splits | 0 |
| Cross-split image hash collisions | 0 |
| Cross-split source path collisions | 0 |
| Cross-split basename collisions | 0 |
| Cross-split nearby samples, same group+modality, frame-index delta ≤ 10 | 7,287 |

Example evidence from the manifest:

```text
RGBT_test_20190925_111757_1_1_infrared_110.jpg  → test
RGBT_test_20190925_111757_1_1_infrared_115.jpg  → train

RGBT_test_20190925_111757_1_1_infrared_190.jpg  → train
RGBT_test_20190925_111757_1_1_infrared_195.jpg  → val
```

The source-frame gaps reflect the sparse sampling in the prepared image
dataset; they are still neighboring observations from the same inferred video
sequence. The audit does not claim duplicate pixels: global image hashes are
unique.

## Halmstad V_DRONE_001

The exact string `V_DRONE_001` occurs zero times in the processed detector
manifest. That is evidence that this name is not directly present in the
current train rows, but it is not a proof of source independence: the selected
Halmstad archive sequence is not linked to the processed manifest by a durable
archive/video provenance key. The correct status remains
`SPLIT_UNVERIFIED` for independent evaluation of the selected sequence.

## Reproduction

```bash
python scripts/audit_split_leakage.py \
  --manifest data/processed/drone-single-class/manifest.json \
  --output .runtime/scope04_split_audit.json
```

No split was changed by this audit.
