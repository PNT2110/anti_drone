# Scope 17 — Input Audit

Scope 17 giữ nguyên V1, V2, V3 candidate gốc, checkpoint V1, archive nguồn và toàn bộ báo cáo Scope 13–16. Baseline trước repair:

- V3 manifest: `b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc`.
- V3 split registry: `57ffb56effd35ad65aad9d163e586ebd8c9f9f1f19c93a86d5fd7619d72cff3d`.
- Scope 16 label preflight: `PREFLIGHT_BLOCKED`, 25.527 source-object/empty-label mismatches.
- V1/V2/checkpoint baseline: PASS theo `.runtime/scope15/input_baseline.json`.

Candidate gốc có 30.227 samples, train/val/test `12.142/8.237/9.848`, 318 sequence và 63 prefix; quarantine `6.505/4.172` tiếp tục bị loại. `SOURCE_SEQUENCE_DISJOINT=VERIFIED`, `CANDIDATE_PREFIX_DISJOINT=VERIFIED`, `SESSION_DISJOINT=UNVERIFIED`; checkpoint V1 vẫn `SPLIT_UNVERIFIED`.

Artifact root-cause audit và sample selection nằm tại `.runtime/scope17/`; không overwrite label hiện tại.
