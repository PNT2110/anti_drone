# Scope 13 — Final Report

## Decision

**PARTIALLY COMPLETE.** Archive/source-sequence provenance is resolved for all assigned RGBT rows. Session provenance is not resolved because `Anti-UAV300.tar` does not define an explicit session identifier for directories sharing a date/time prefix.

## Required answers

1. **Rows mapped strongly:** 30,227/30,227 map to an exact `Anti-UAV300.tar` archive directory, modality member, and source frame index with valid annotation JSON bounds. Six representative video decodes corroborate the naming/frame rule.
2. **Groups source-verified:** 318/318 at source-sequence-directory level. Session-level identity remains unverified.
3. **59 candidate prefixes:** 0 confirmed shared sessions; 59 confirmed distinct archive source sequences; 0 unresolved at the sequence-directory level. All 59 have unresolved session relationship.
4. **47 cross-split prefixes:** 0 confirmed collisions; 47 remain UNKNOWN at session level.
5. **Confirmed cross-split sequence collision:** 0.
6. **Confirmed cross-split session collision:** 0; 47 session relationships are unresolved, not counted as independent.
7. **V2 group rule:** no change is justified for the confirmed sequence-level rule. A future session-disjoint rule may need authoritative session metadata, but equal timestamps alone are insufficient.
8. **Enough evidence for V3:** enough to design a source-sequence-aware V3 proposal; not enough to approve a session-disjoint V3 or create it. No V3 was generated.
9. **Tests:** 73 passed, 1 skipped; compileall and diff check PASS.
10. **Baseline:** all V1, V2, executable V2, and Scope 12 provenance checksums listed in `SCOPE13_INPUT_AUDIT.md` remain unchanged.

## Boundaries preserved

The 6,505 quarantine samples remain unchanged. V1, V2, executable V2, checkpoint, tracker, gate, Halmstad identity ground truth, and historical reports were not modified. No YOLO training, Pi/camera run, or Git commit/push was performed. V1 checkpoint status remains `SPLIT_UNVERIFIED`.

Research & Design should review [SOURCE_ARCHIVE_MAPPING.md](SOURCE_ARCHIVE_MAPPING.md), [SESSION_PREFIX_AUDIT.md](SESSION_PREFIX_AUDIT.md), and [CROSS_SPLIT_COLLISION_REPORT.md](CROSS_SPLIT_COLLISION_REPORT.md) before authorizing a V3 split or new training run.
