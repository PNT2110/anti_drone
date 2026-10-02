# Scope 16 — Input Audit

Kết luận: baseline input **PASS**, nhưng Scope 16 bị chặn ở label preflight trước epoch đầu tiên.

Candidate V3 manifest hash hiện tại: `b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc`.

Candidate V3 split registry hash hiện tại: `57ffb56effd35ad65aad9d163e586ebd8c9f9f1f19c93a86d5fd7619d72cff3d`.

Expected counts vẫn đúng: train `12,142`, val `8,237`, test `9,848`, assigned `30,227`; quarantine `6,505` samples / `4,172` groups bị loại. Scope 15 direct-disk audit vẫn PASS.

Các trạng thái được giữ nguyên:

- `SOURCE_SEQUENCE_DISJOINT = VERIFIED` theo Scope 13/15 mapping.
- `CANDIDATE_PREFIX_DISJOINT = VERIFIED` theo policy B.
- `SESSION_DISJOINT = UNVERIFIED`.
- Checkpoint V1 = `SPLIT_UNVERIFIED`.

Baseline Scope 15 input audit và các checksum V1/V2/V3/checkpoint được ghi tại `.runtime/scope15/input_baseline.json`. Không tái tạo split, không sửa ảnh/label, không đưa quarantine trở lại.
