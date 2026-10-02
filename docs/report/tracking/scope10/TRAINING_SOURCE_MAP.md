# Scope 10 — Training Source Map

Checkpoint provenance was read from the actual files, not inferred from filenames. The release/model-selection record ties the current YOLOv8n checkpoint to `data/processed/drone-single-class/manifest.json`; that manifest has source counts `base=34,398` and `my_dataset=2,334`, but does not preserve an archive-member/video key for the `base` rows.

| Source archive | Classification | Evidence | Scope 10 consequence |
|---|---|---|---|
| `my_dataset.tar.xz` | **CONFIRMED TRAIN SOURCE** | Manifest metadata names this archive and 2,334 rows have `source=my_dataset`; archive was eligible for training | Not independent |
| `Anti-UAV300.tar` | **UNVERIFIED** | Present in source inventory, but no archive-member mapping to checkpoint training rows or exclusion record | Diagnostic only |
| `DUT-Anti-UAV.tar` | **UNVERIFIED** | Same limitation; no durable source-member key in training manifest | Diagnostic only |
| `Drone-vs-Bird.tar` | **UNVERIFIED** | Same limitation; filename absence is not proof of disjointness | Diagnostic only |
| `Halmstad-Drone.tar` | **UNVERIFIED** | Halmstad archive is available and selected members are unique, but the checkpoint manifest has no archive/video mapping | Diagnostic only |
| `UAV-CB.tar` | **UNVERIFIED** | Same limitation; no durable source-member key | Diagnostic only |

No source archive is classified `CONFIRMED SOURCE-DISJOINT`. The exact Halmstad name `V_DRONE_001` is absent from the processed manifest, but that remains insufficient evidence because the manifest lacks the archive/member relationship. pHash or filename absence is not used as source identity proof.

Machine-readable map: `.runtime/scope10/training_source_map.json`.

Relevant provenance records:

- model training provenance: `artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2/anti_drone_provenance.json`;
- model-selection provenance: `artifacts/benchmarks/model-selection/yolov8n/provenance.json`;
- release provenance: `artifacts/releases/yolov8n/release.json`.

Conclusion: `NO INDEPENDENT TEMPORAL VALIDATION SEQUENCE PROVEN`.
