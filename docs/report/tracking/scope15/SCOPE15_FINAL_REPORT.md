# Scope 15 — Final Report

## Kết luận

Candidate V3 đạt **V3_CANDIDATE_READY** cho mục đích loader/training-readiness review: materialization hoàn tất, direct-disk audit PASS, loader smoke PASS, original source boundary được giữ nguyên và baseline V1/V2/checkpoint không đổi.

Trạng thái này **không** có nghĩa là `SESSION_INDEPENDENT`, production-ready hoặc được phép tự động train. `SESSION_DISJOINT=UNVERIFIED`, checkpoint V1 vẫn `SPLIT_UNVERIFIED`, và Halmstad vẫn `diagnostic_only`.

## Trả lời acceptance gate

1. Có đúng 30,227 ảnh: **Có**, assigned đúng một lần.
2. Counts chính sách B: **Có** — train 12,142; val 8,237; test 9,848.
3. Original partition được bảo vệ: **Có** — original train/val/test ánh xạ cùng tên split.
4. Source sequence và candidate prefix overlap: **0 / 0**.
5. Quarantine leakage: **0**; 6,505 samples và 4,172 groups tiếp tục bị loại.
6. Ảnh/label đọc được: **Có** — direct audit/hash/label PASS; loader scan không có corrupt file.
7. `data.yaml` và loader: **PASS**; loader đọc đủ ba split và load ba pretrained weights.
8. Bằng chứng độc lập session: **30,227 samples vẫn SESSION_DISJOINT=UNVERIFIED**; provenance archive/member là confirmed, nhưng không được suy diễn thành session ID thật.
9. Baseline V1/V2/checkpoint: **giữ nguyên checksum** theo `.runtime/scope15/input_baseline.json`.
10. Tests: **80 passed, 1 skipped**; compileall **PASS**; `git diff --check` **PASS**. Input/materialization/audit/finalization/loader đều PASS.
11. Điều kiện BLOCKED trước training: **Còn policy gate** — cần Research & Design phê duyệt, cần giữ test locked và chưa được kích hoạt production; không có lỗi materialization/audit/loader.

## Artifact chính

- Candidate: `/run/media/pnt/APP/anti_drone/data/processed/drone-single-class-v3-candidate/`.
- Manifest hash: `b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc`.
- Split registry hash: `57ffb56effd35ad65aad9d163e586ebd8c9f9f1f19c93a86d5fd7619d72cff3d`.
- Direct audit: `.runtime/scope15/direct_disk_audit.json`, PASS.
- Loader smoke: `.runtime/scope15/loader_smoke.json`, PASS.
- Six configs: `configs/training/scope15/`, tất cả `PREPARED_NOT_TRAINED`.

Không Git commit/push. Không thay tracker, gate, checkpoint, V1/V2 hoặc production dataset.
