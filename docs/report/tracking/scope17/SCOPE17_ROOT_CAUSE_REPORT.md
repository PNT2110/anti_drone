# Scope 17 — Root Cause Report

## Kết luận

Nguyên nhân gốc được xác minh ở ranh giới tạo V1: `scripts/prepare_dataset.py` không chuyển annotation Anti-UAV300 thành YOLO label cho `source=base`; hàm `link_or_empty()` chỉ pass-through label đã tồn tại. Chỉ nhánh `my_dataset` mới gọi `normalize_single_class_label()`.

Converter Anti-UAV300 được tìm thấy tại `/home/pnt/Desktop/antidrone/drone-rocket/scripts/prepare_anti_uav300_yolo.py`. Converter này dùng frame index 0-based trực tiếp, đọc `gt_rect` dạng `[x,y,w,h]` pixel, chuẩn hóa theo kích thước ảnh, và chỉ ghi label rỗng khi `exist` là false. Output naming của converter là `<sequence>__f<frame:06d>.txt`, không trùng convention hiện tại `RGBT_<split>_<date>_<time>_<stream>_<sequence>_<modality>_<frame>.txt`. Vì vậy các label RGBT hiện tại không phải output trực tiếp của converter đã kiểm tra; producer lịch sử cụ thể của thư mục sparse này không còn được lưu trong repo.

## Kiểm chứng mapping và tọa độ

- 30.227/30.227 frame map đúng filename frame suffix, mapping Scope 13, source JSON và modality.
- 636 annotation JSON được đọc trực tiếp từ `Anti-UAV300.tar`.
- Tất cả 30.227 frame có `exist=1` và một `gt_rect` hợp lệ.
- Visible: 14.713 ảnh, 1920×1080. Infrared: 15.514 ảnh, 640×512.
- Tất cả rectangle dương và nằm trong biên; không cần clip.
- Frame index 1-based bị bác bỏ: mapping 0-based khớp source frame/rectangle.
- Source sequence không có frame nhiều box trong 30.227 rows; `source_multi_box_frames=0`.

## Nhãn hiện tại

- 4.700 ảnh có label object, tổng 4.790 objects.
- 25.527 ảnh label rỗng nhưng source có target: `MISSING_OR_CORRUPT_ANNOTATION`.
- 4.700 label không rỗng cũng không khớp source rectangle theo tolerance `5e-6`: `EXISTING_LABEL_MISMATCH`.
- 0 source-confirmed negative; 0 source annotation unresolved.

Evidence chi tiết: `.runtime/scope17/existing_label_mismatches.jsonl` và `.runtime/scope17/sample_selection.json`.
