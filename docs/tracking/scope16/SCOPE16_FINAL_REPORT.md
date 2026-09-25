# Scope 16 — Final Report

## Kết luận

Scope 16 **PREFLIGHT_BLOCKED / PARTIALLY COMPLETE**, không đạt `TRAINING_COMPLETE`. Không một epoch nào được khởi động.

## Lý do chặn

Đối chiếu 30,227 sample với 636 annotation JSON trong `Anti-UAV300.tar` cho thấy:

- `30,227/30,227` frame có `exist=1` và `gt_rect` hợp lệ trong source annotation.
- Chỉ `4,700` ảnh có ít nhất một processed YOLO label; tổng `4,790` object.
- `25,527` ảnh có label rỗng nhưng source annotation xác nhận target tồn tại.
- `0` ảnh được xác nhận là `CONFIRMED_NEGATIVE`.
- Mismatch xuất hiện ở train/val/test và cả visible/infrared, nên là lỗi có tính hệ thống.

Theo yêu cầu Scope 16, đây là `MISSING_OR_CORRUPT_ANNOTATION`, phải dừng trước training. Không tự sửa nhãn, không xóa ảnh, không đổi split và không đưa quarantine trở lại.

## Ma trận run

Sáu cấu hình YOLOv8n/YOLOv11n/YOLOv26n ở 640/480 đều được ghi nhận `NOT_STARTED_LABEL_PREFLIGHT`; không có checkpoint, best/last hash, epoch, loss hoặc validation metric. Vì vậy không được tuyên bố “six runs complete”.

## Bảo toàn dữ liệu và giới hạn

Candidate manifest/split registry vẫn đúng checksum Scope 15; quarantine vẫn bị loại; V3 test chưa được dùng. `SOURCE_SEQUENCE_DISJOINT` và `CANDIDATE_PREFIX_DISJOINT` vẫn VERIFIED, `SESSION_DISJOINT` vẫn UNVERIFIED. Checkpoint V1 vẫn `SPLIT_UNVERIFIED`. Không có thay đổi V1/V2/V3 data, tracker, gate, model production, Pi/camera hoặc Git history.

## Artifact bàn giao

- [SCOPE16_LABEL_PREFLIGHT.md](SCOPE16_LABEL_PREFLIGHT.md)
- [SCOPE16_TRAINING_MATRIX.md](SCOPE16_TRAINING_MATRIX.md)
- [SCOPE16_VALIDATION_REPORT.md](SCOPE16_VALIDATION_REPORT.md)
- Machine-readable evidence: `.runtime/scope16/label_preflight.json`, `.runtime/scope16/label_source_mismatches.jsonl`, `.runtime/scope16/training_matrix.json`.

Training chỉ có thể mở lại sau khi nguồn nhãn được điều tra/sửa ở scope được phê duyệt, checksum candidate thay đổi có kiểm soát, và toàn bộ label preflight chạy lại đạt PASS.
