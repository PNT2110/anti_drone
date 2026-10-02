# Scope 11 — Final Report

Audit date: 2026-09-22. Repository: `/run/media/pnt/APP/anti_drone`.

## Outcome

**COMPLETE as a quarantine accounting audit; no split or training approval.** All 6,505 samples / 4,172 groups are present in the mapping with an explicit status and evidence trail. All remain `UNRESOLVED` under the required conservative rules:

- confirmed source sequence: **0**;
- confirmed independent image: **0**;
- possible match: **0**;
- unresolved: **6,505**.

The result is not a claim that the data are independent. `SPLIT_UNVERIFIED` remains unchanged. No V2 split was regenerated, no sample was assigned to train/val/test, and no checkpoint or source media was modified.

## Main evidence

- DUT: 4,171/4,171 exact matches to expected detection archive member and V1 image hash; all tracking JPGs were scanned by content hash, with no exact tracking match. Same-number filename candidates are clues only.
- `my_dataset`: 2,334/2,334 exact matches to flat archive image members; 2,327 labels were present, but no source video/session/frame metadata exists. Independence is therefore unproven.
- Quarantine vs 318 verified RGBT groups: 0 exact hash collisions, 0 exact source-path collisions, and no proven `SOURCE_GROUP_ALIAS`.
- Checkpoint relation: sample-level V1 split membership is known; source-sequence relation is not encoded in checkpoint provenance. No Halmstad independence inference was made.

## Artifacts and commands

Primary command:

```text
python scripts/run_scope11_provenance_audit.py
python -m pytest -q tests/test_scope11_provenance.py
python -m pytest -q
python -m compileall -q scripts src tests
git diff --check
```

Mapping and evidence:

- `.runtime/scope11/quarantine_provenance.csv`
- `.runtime/scope11/quarantine_provenance_summary.json`
- `.runtime/scope11/source_group_collisions.json`
- `.runtime/scope11/checkpoint_provenance.json`
- `.runtime/scope11/input_audit.json`
- `.runtime/scope11/output_checksums.json`

No Git commit or push was performed.

## Recommendation for a future V2 revision

No sample or group is recommended for automatic promotion from this audit. A future revision may review the 4,171 DUT samples and 2,334 `my_dataset` samples with additional source metadata, annotation manifests, or human sequence identity review. Any proposed group must be re-audited for source collision before it is eligible for a new split. This report does not create that split.
