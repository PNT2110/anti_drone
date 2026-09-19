# Anti-drone phase runbooks

Trạng thái bộ tài liệu: `TODO`

Các file trong thư mục này là runbook thực thi. Mỗi phase phải được hoàn tất
theo đúng thứ tự và phải đạt acceptance gate trước khi chuyển phase tiếp theo.

## Dependency

```text
Phase 00 -> Phase 01 -> Phase 02 -> Phase 03
                                      |
                                      v
                              Phase 04 -> Phase 05 -> Phase 06
                                      ^
                                      |
                                  Phase 07
```

## Bảng trạng thái

| Phase | Nội dung | Input chính | Output chính | Gate | Trạng thái |
|---|---|---|---|---|---|
| 00 | Chuẩn hóa repository | Cấu trúc hiện có | Baseline report | Repo và môi trường kiểm tra được | `TODO` |
| 01 | Nhập và audit dataset | Archive hiện có | Dataset v1 hợp lệ | Audit `valid` | `TODO` |
| 02 | Train GPU | Dataset v1 | Checkpoint | Train hoàn tất | `TODO` |
| 03 | Evaluation/model selection | Checkpoint | Model winner | Threshold khóa | `TODO` |
| 04 | Export/parity | Model winner | ONNX/NCNN/TFLite | Output tương đương | `TODO` |
| 05 | Pi/camera/tracker | Runtime artifacts | Live pipeline | Camera chạy ổn định | `TODO` |
| 06 | Benchmark/release | Pi pipeline | Benchmark report | Release candidate | `TODO` |
| 07 | Retrain/maintenance | Data/model mới | Version tiếp theo | Không phá baseline | `TODO` |

## Quy ước trạng thái

- `TODO`: chưa bắt đầu.
- `RUNNING`: đang thực hiện, chưa được coi là đạt.
- `BLOCKED`: bị chặn; phải ghi nguyên nhân và hướng xử lý.
- `DONE`: đã đạt toàn bộ acceptance gate và có provenance.

Mỗi lần đổi trạng thái phải cập nhật file phase tương ứng và ghi thời gian,
người thực hiện, commit hoặc checksum liên quan.

## Quy tắc chung

1. Không sửa dataset v1 sau khi đã khóa manifest.
2. Không dùng test set để chọn model hoặc threshold.
3. Không train trên Raspberry Pi.
4. Không ghi số benchmark khi chưa ghi environment và protocol.
5. Mọi artifact phải truy ngược được về checkpoint, dataset manifest và config.
6. Nếu gate không đạt, quay lại phase được chỉ định thay vì bỏ qua gate.

## Dataset invariant

Phase 01 phải áp dụng các invariant sau trước khi được đánh dấu `DONE`:

- Tất cả thư mục dưới `data/import_data_rar/` đã được inventory.
- Source tải dở chỉ nằm trong quarantine, không tham gia split.
- Target split là `train 70% / val 20% / test 10%`.
- `my_dataset` tồn tại và toàn bộ sample hợp lệ của nó nằm trong train.
- Không có image, image hash hoặc video/sequence group overlap giữa ba split.
