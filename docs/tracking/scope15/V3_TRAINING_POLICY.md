# V3 Training Policy — Prepared, Not Executed

Sáu cấu hình riêng được tạo dưới `configs/training/scope15/`:

- YOLOv8n: 480, 640.
- YOLOv11n: 480, 640.
- YOLOv26n: 480, 640.

Mỗi config dùng candidate V3 `data.yaml`, seed 42, batch 16, device 0, workers 4, epochs 100, exact pretrained weight hash và output root riêng `artifacts/experiments/scope15-v3/...`; không tái sử dụng output Scope 12. Tất cả có `status=PREPARED_NOT_TRAINED`, `training_not_run=true`, và artifact `.runtime/scope15/finalization.json` xác nhận không có training run.

Nếu Scope sau cho phép train: chỉ V3 train được cập nhật weights; V3 val dùng chọn checkpoint/tham số; V3 test khóa cho tới khi quyết định freeze; chỉ đánh giá test sau freeze. Resume chỉ từ `last.pt` của chính run/model/size. Mỗi run phải lưu manifest hash, split hash, mapping, exact weight, package versions và seed.

Checkpoint V1 vẫn `SPLIT_UNVERIFIED`, không được tự động xem là independent. Ba video Halmstad vẫn `diagnostic_only`; candidate V3 không làm thay đổi kết luận đó. V3 candidate chưa phải production và chưa phải `SESSION_INDEPENDENT`.
