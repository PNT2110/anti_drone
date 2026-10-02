# Scope 12 — Executable Dataset Audit

Direct-on-disk audit result: **PASS**.

- 30,227 output images found with the exact expected split counts.
- 30,227 corresponding labels present; no missing label was created or hidden.
- No quarantine row leaked into train, val, or test.
- No duplicate output/source IDs.
- No exact source-path or source-hash overlap between splits.
- All 318 verified groups remain entirely within one split; zero groups cross splits.
- All physical output image hashes match the V2 source image hashes.
- Class IDs are 0 and normalized YOLO boxes are positive and within image bounds.
- 78 boundary edges in 77 label files are within a `1e-6` decimal-rounding tolerance of 0/1; labels were not clamped or rewritten.
- `data.yaml` points to the executable dataset.

The direct audit is `scripts/audit_scope12_executable_dataset.py`; its JSON result is `data/processed/drone-single-class-v2-executable/executable_dataset_audit.json`.

This validates the accepted group-disjoint assignment contract. It does not promote the unresolved archive/session provenance into source-independent evidence.
