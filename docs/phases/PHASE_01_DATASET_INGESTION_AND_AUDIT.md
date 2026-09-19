# Phase 01 — Dataset ingestion and audit

Trạng thái: `TODO`

## Mục tiêu

Tạo dataset v1 có manifest, annotation YOLO hợp lệ, split không leakage và audit
có trạng thái `valid`.

## Phạm vi

Xử lý các archive hiện có, chuyển annotation về một class `drone`, phân biệt
positive/negative/hard-negative và tạo runtime metadata.

Không train, không chọn model và không chạy inference camera trong phase này.

## Điều kiện đầu vào

- Phase 00 đã `DONE`.
- Tất cả thư mục trực tiếp dưới `data/import_data_rar/` đã được inventory.
- Các source đang tải dở hoặc chưa có checksum hoàn chỉnh được ghi nhận nhưng
  chưa được đưa vào tập đủ điều kiện để chia split.
- Source `my_dataset` phải tồn tại và phải có dữ liệu hợp lệ.
- Config dataset: `configs/datasets/drone-single-class.yaml`.

## Chính sách dữ liệu

```text
class 0 = drone
```

- Frame có drone phải có box sát vật thể.
- Frame không có drone chỉ được coi là negative khi nguồn hoặc người review xác nhận.
- Bird và vật thể gây nhầm là hard-negative nếu không phải drone.
- Không tự biến label rỗng thành negative khi chưa audit.
- Không chia frame gần nhau của cùng video sang nhiều split.

## Chính sách split bắt buộc

Sau khi loại ảnh lỗi và duplicate toàn cục, dataset phải được chia theo mục tiêu:

```text
train = 70%
val   = 20%
test  = 10%
```

Các quy tắc không được thay đổi:

1. `my_dataset` là nguồn bắt buộc của train.
2. Toàn bộ sample hợp lệ của `my_dataset` được ghim vào `train`; không đưa
   sample của nguồn này sang `val` hoặc `test`.
3. Phần dữ liệu còn lại được phân bổ để tổng tỷ lệ cuối cùng gần 70/20/10 nhất.
4. Nếu số sample của `my_dataset` lớn hơn quota train 70%, phase phải `BLOCKED`
   thay vì tự ý đưa `my_dataset` vào val/test hoặc phá tỷ lệ.
5. Split theo source/video/sequence trước, sau đó kiểm tra lại quota theo image.
6. Không để cùng một ảnh, cùng hash ảnh hoặc cùng frame sequence xuất hiện ở
   nhiều split.
7. Duplicate phải được loại toàn cục trước khi tính 70/20/10, không deduplicate
   riêng từng source.
8. Nếu group lock khiến tỷ lệ lệch nhẹ, phải ghi rõ target count, actual count,
   sai lệch và các group gây lệch trong `split_registry.json`.

Tỷ lệ được tính trên các source đã xác minh hoàn chỉnh. Source tải dở chỉ nằm
trong inventory/quarantine và không được làm thay đổi quota train/val/test.

## Lệnh thực hiện

```bash
cd /run/media/pnt/APP/anti_drone

# Inventory toàn bộ entry trực tiếp dưới source root và checksum file
find data/import_data_rar -mindepth 1 -maxdepth 1 \
  -printf '%y %p %s bytes\n' | sort
find data/import_data_rar -type f -print0 \
  | sort -z \
  | xargs -0 sha256sum > .runtime/datasets/source_sha256sums.txt

# Kiểm tra nội dung archive trước khi giải nén
tar -tf data/import_data_rar/Drone-vs-Bird.tar | sed -n '1,80p'
tar -tf data/import_data_rar/Halmstad-Drone.tar | sed -n '1,80p'
tar -tf data/import_data_rar/UAV-CB.tar | sed -n '1,80p'

# Chạy công cụ ingest/audit sau khi source code đã được triển khai
anti-drone dataset inventory --input data/import_data_rar
anti-drone dataset prepare --dataset drone-single-class \
  --input data/import_data_rar \
  --output-root data/processed/drone-single-class
anti-drone dataset split --dataset drone-single-class \
  --root data/processed/drone-single-class \
  --train-ratio 0.70 --val-ratio 0.20 --test-ratio 0.10 \
  --force-train-source my_dataset \
  --group-by source,video,sequence \
  --dedupe global
anti-drone dataset audit --dataset drone-single-class \
  --root data/processed/drone-single-class \
  --hash-images
```

Nếu dataset có format riêng, converter phải ghi source file, annotation count và
quy tắc chuyển đổi vào manifest; không sửa archive gốc.

## Output bắt buộc

```text
.runtime/datasets/drone-single-class/
├── data.yaml
├── audit.json
├── manifest.json
├── split_registry.json
└── label_statistics.json
```

Dataset processed cục bộ phải có:

```text
data/processed/drone-single-class/
├── images/train
├── images/val
├── images/test
├── labels/train
├── labels/val
└── labels/test
```

## Checklist

- [ ] Mọi source archive có checksum.
- [ ] Archive chưa hoàn chỉnh nằm ngoài train.
- [ ] Annotation đã chuyển về YOLO.
- [ ] Chỉ có class ID `0`.
- [ ] Không có box ngoài biên hoặc box rỗng sai format.
- [ ] Image/label pairs được kiểm tra.
- [ ] Ảnh trùng đã được ghi nhận.
- [ ] Duplicate đã được loại toàn cục trước khi split.
- [ ] `my_dataset` tồn tại và toàn bộ sample hợp lệ nằm trong train.
- [ ] Split theo video/sequence.
- [ ] Target ratio là 70/20/10.
- [ ] Actual ratio và sai lệch đã ghi trong split registry.
- [ ] Không có image/hash/frame sequence trùng giữa train/val/test.
- [ ] Kích thước box đã thống kê.
- [ ] `audit.json` có `status: valid`.

## Acceptance gate

Chỉ chuyển phase khi audit `valid`, manifest đầy đủ, `my_dataset` nằm trong train,
split registry bất biến, tỷ lệ 70/20/10 đã được kiểm tra và không có image/hash/
sequence overlap giữa train/val/test. Archive tải dở không được nằm trong danh
sách train.

## Dừng hoặc quay lại

- Dừng nếu thiếu annotation hoặc không xác định được ý nghĩa label rỗng.
- Dừng nếu không tìm thấy `my_dataset` hoặc `my_dataset` không có sample hợp lệ.
- Dừng nếu `my_dataset` vượt quota train khiến không thể giữ policy 70/20/10.
- Quay lại converter nếu class ID/format không hợp lệ.
- Quay lại split nếu phát hiện frame của cùng video nằm ở nhiều split.
- Quay lại dedup nếu phát hiện cùng hash ảnh ở nhiều split.
- Quay lại nguồn dữ liệu nếu checksum thay đổi.

## Provenance

Lưu archive checksum, source metadata, converter version, số image/label/box,
empty-label count, duplicate count, `my_dataset` sample count, target/actual
split counts, overlap report, split rule, command và thời gian audit.
