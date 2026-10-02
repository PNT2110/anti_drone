# Scope 12 — Final Report

## Decision

**Technical dataset status: READY FOR A CONTROLLED NEW TRAINING RUN.**

This is not source-independence approval and not an instruction to start training. The output is an executable copy of only the accepted 30,227 V2 assigned rows. The 6,505 quarantined rows and 4,172 groups remain excluded.

## Answers to required questions

1. **Materialized:** 30,227/30,227 images, with 21,168 train, 6,096 val, and 2,963 test images.
2. **Source evidence incomplete:** all 30,227 have local source path + matching image hash; 0 have archive/member proof in the manifest; 318 groups remain archive-level unverified. There are 59 candidate shared-session prefixes, 47 crossing splits, not proven aliases.
3. **Aliases/collisions:** zero proven group aliases; zero cross-split group collisions; zero exact source-path/hash overlap. The candidate session warning remains open.
4. **`data.yaml`/loader:** PASS. Direct disk audit PASS; Ultralytics 8.4.125 loader read all three splits; exact YOLOv8n, YOLOv11n, and YOLOv26n weights loaded.
5. **Quarantine leakage:** zero.
6. **Supported configurations:** all six prepared: `yolov8n_640`, `yolov8n_480`, `yolov11n_640`, `yolov11n_480`, `yolo26n_640`, `yolo26n_480`.
7. **Resume/provenance:** each config has a unique output directory, exact weight hash, V2 manifest/registry hashes, seed 42, excluded quarantine counts, sample IDs, validation-only selection policy, and same-run `last.pt`-only resume rule.
8. **READY or BLOCKED:** technically READY for a controlled new training run; source-independent readiness is **not** claimed. Research & Design review is required because archive/member provenance is absent and candidate sessions cross splits.
9. **Tests:** 67 passed, 1 skipped; compileall PASS; diff check PASS.
10. **Baseline unchanged:** V1 manifest/registry/audit/data.yaml, V2 manifest/registry/audit, checkpoint, tracker, gate, and historical reports retain their locked hashes/content.

## Boundary conditions

No YOLO training was run. No checkpoint was replaced. No source image/label was modified. No V2 assignment was changed. No Halmstad video was used as an independent test, and no generalization claim is made.

Review artifacts requested for Research & Design:

- [SCOPE12_SOURCE_PROVENANCE.md](SCOPE12_SOURCE_PROVENANCE.md)
- [SCOPE12_EXECUTABLE_DATASET_AUDIT.md](SCOPE12_EXECUTABLE_DATASET_AUDIT.md)
- [SCOPE12_TRAINING_READINESS.md](SCOPE12_TRAINING_READINESS.md)
