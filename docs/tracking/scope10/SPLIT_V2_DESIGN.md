# Scope 10 Corrective — Split V2 Design

V2 is a manifest-only group-disjoint split derived from the immutable V1 manifest. It is not activated for training and does not replace `data/processed/drone-single-class/`.

Parameters:

```text
source manifest: data/processed/drone-single-class/manifest.json
grouping rule: scope10-rgbt-sequence-group-v1
split algorithm: scope10-seeded-shuffle-largest-deficit-v1
seed: 42
target: train 70%, val 20%, test 10%
unverified policy: quarantine
```

The 318 verified sequence groups are sorted, shuffled with a local seeded RNG, then assigned intact to the split with the largest remaining sample deficit. Group boundaries are never broken to force exact ratios. The 6,505 unverified samples receive `split=quarantine` and cannot be used to claim source-disjoint validation/test.

V2 contains `manifest.json`, `split_registry.json`, `audit.json` and `output_checksums.json`. `data.yaml` is intentionally not created: this is a manifest-only artifact and no executable image path is fabricated. Source images and V1 artifacts remain untouched.
