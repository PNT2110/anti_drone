# Scope 17 — Final Report

## Kết luận

Scope 17 hoàn tất root-cause audit và tạo một label-repair candidate riêng. Kết quả: **LABEL_READY (candidate-only)**. Không train YOLO.

## Trả lời acceptance questions

1. Nguyên nhân 25.527 label rỗng: V1 builder pass-through label base có sẵn qua `link_or_empty()`; nó không chuyển annotation Anti-UAV300 cho base rows. Converter source được kiểm tra có contract khác và không phải producer trực tiếp của các file RGBT hiện tại.
2. Mất nhãn thực sự: **25.527** source-confirmed objects bị label rỗng.
3. Negative source xác nhận: **0**.
4. Existing label sai/không khớp: **4.700 ảnh / 4.700 label không rỗng**, tổng 4.790 object cũ; toàn bộ không khớp source rectangle trong tolerance.
5. Label sửa bằng annotation nguồn: **30.227**.
6. Sample không thể xác minh: **0** trong mapping hiện tại; session-level independence vẫn `UNVERIFIED`.
7. Ảnh/split/quarantine: giữ nguyên; V3 gốc không bị overwrite, counts vẫn 12.142/8.237/9.848, quarantine 6.505/4.172 không xuất hiện.
8. Direct audit và loader: **PASS/PASS**.
9. V1/V2/V3 gốc/checkpoint: checksum giữ nguyên theo baseline audit; checkpoint V1 vẫn `SPLIT_UNVERIFIED`.
10. Test cuối: **85 passed, 1 skipped**; compileall và `git diff --check` **PASS**.
11. Trạng thái: repair candidate đạt **LABEL_READY**, không phải production và không tự mở lại training.

## Artifact bàn giao

- [SCOPE17_ROOT_CAUSE_REPORT.md](SCOPE17_ROOT_CAUSE_REPORT.md)
- [SCOPE17_LABEL_REPAIR_AUDIT.md](SCOPE17_LABEL_REPAIR_AUDIT.md)
- [SCOPE17_COORDINATE_CONTRACT.md](SCOPE17_COORDINATE_CONTRACT.md)
- Candidate: `/run/media/pnt/APP/anti_drone/data/processed/drone-single-class-v3-labelrepair-candidate/`.
- Root evidence: `.runtime/scope17/root_cause_audit.json`, `.runtime/scope17/existing_label_mismatches.jsonl`.
- Repair audit: `.runtime/scope17/label_repair_audit.json`.

Halmstad vẫn `diagnostic_only`; không tuyên bố `SESSION_INDEPENDENT`; không Git commit/push. Scope 16 chỉ nên mở lại sau khi Research & Design kiểm tra Scope 17 audit.
