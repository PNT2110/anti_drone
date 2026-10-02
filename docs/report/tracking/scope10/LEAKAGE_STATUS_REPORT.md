# Scope 10 — Leakage Status

The older prepared detector dataset remains unchanged. Scope 04 found:

- 36,732 image rows and 4,490 inferred groups;
- 318 groups present in more than one logical split;
- 30,227 rows belonging to those overlapping groups;
- zero exact cross-split image-hash collisions in that audit;
- zero exact `(group, modality, source-frame)` collision count in that audit, but 7,287 nearby same-group/same-modality samples with frame delta ≤10.

This is a sequence/group split-independence problem, not evidence that the new temporal manifest itself is leaking. The new manifest does not assign train/val/test and does not inherit the old 70/20/10 split. However, source-disjointness against the frozen checkpoint cannot be proven because checkpoint training provenance stops at the processed image manifest and has no archive/member/video key.

Scope 10 therefore makes no independent-validation claim. It does not modify `prepare_dataset.py`, regenerate the old split, alter the checkpoint, or retrain. A future production benchmark should first decide whether to create a source-group-disjoint split and retrain a checkpoint with durable source provenance.

Machine-readable collision classes are kept separate in `.runtime/scope10/temporal_validation_audit.json`: exact duplicate leakage, same-source-video collision, same-sequence collision, and provenance-unknown warnings.
