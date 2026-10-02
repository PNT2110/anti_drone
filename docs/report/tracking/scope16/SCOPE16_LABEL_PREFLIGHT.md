# Scope 16 — Label Preflight

Script: `scripts/scope16_label_preflight.py`. Annotation nguồn được đọc trực tiếp từ `data/import_data_rar/Anti-UAV300.tar`, không extract hàng loạt và không sửa dataset.

Kết quả: **PREFLIGHT_BLOCKED**; `training_started=false`.

| Split | Ảnh | Có label object | Label rỗng | Source target confirmed | Source label consistent | Mismatch |
|---|---:|---:|---:|---:|---:|---:|
| train | 12,142 | 2,084 | 10,058 | 12,142 | 2,084 | 10,058 |
| val | 8,237 | 1,429 | 6,808 | 8,237 | 1,429 | 6,808 |
| test | 9,848 | 1,187 | 8,661 | 9,848 | 1,187 | 8,661 |
| Total | 30,227 | 4,700 | 25,527 | 30,227 | 4,700 | 25,527 |

Tổng object trong YOLO label là `4,790`, tất cả class ID `0`. Không có class ngoài schema và không có label malformed; lỗi là lỗi hiện diện/đồng nhất với annotation nguồn. Phân bố modality: visible `14,713` ảnh, infrared `15,514` ảnh; cả hai modality đều có mismatch lớn.

Đối với cả `30,227` frame, archive metadata có `exist=1` và `gt_rect` không rỗng. Do đó không có sample nào được chứng minh là `CONFIRMED_NEGATIVE`. Có `25,527` sample được phân loại `MISSING_OR_CORRUPT_ANNOTATION`: source annotation xác nhận target nhưng processed YOLO label rỗng. Không nâng chúng thành `UNVERIFIED_EMPTY_LABEL` hay negative.

Ví dụ bằng chứng đầu tiên: sample `v3-candidate:00000`, source member `Anti-UAV300/data/Anti-UAV300/train/20190925_194211_1_6/visible.json`, frame `255`, source `exist=1`, `gt_rect=[747,489,53,41]`, label processed rỗng. Toàn bộ evidence nằm tại `.runtime/scope16/label_source_mismatches.jsonl`.

Theo gate Scope 16, đây là mất nhãn có tính hệ thống. Không train, không xóa ảnh âm tính, không sửa nhãn và không đổi split.
