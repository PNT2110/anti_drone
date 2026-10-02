# Dataset policy

## Source root

Tất cả thư mục trực tiếp dưới thư mục sau đều phải được inventory:

```text
data/import_data_rar/
```

Không bỏ qua source chỉ vì tên thư mục khác nhau. Mỗi source phải có manifest,
checksum, trạng thái download và trạng thái annotation.

Các source chưa tải xong, file `.crdownload`, archive hỏng hoặc archive không có
checksum hoàn chỉnh được đưa vào quarantine. Chúng vẫn xuất hiện trong inventory
nhưng không được tham gia train/val/test cho đến khi được xác minh.

## Class policy

Dataset v1 là single-class:

```text
0 = drone
```

Bird, airplane, helicopter, cây, cột điện, mái nhà và các vật thể nền không phải
drone được ghi nhận là negative/hard-negative khi có nguồn xác nhận hoặc đã được
review thủ công.

## Split policy

Sau khi chuyển annotation về YOLO và deduplicate toàn cục, chia dataset theo mục tiêu:

| Split | Target |
|---|---:|
| train | 70% |
| val | 20% |
| test | 10% |

`my_dataset` là nguồn bắt buộc của train. Toàn bộ sample hợp lệ của `my_dataset`
được ghim vào train; không đưa source này vào val/test. Các source còn lại được
phân bổ để đạt tỷ lệ 70/20/10 gần nhất.

Tỷ lệ được tính sau khi loại duplicate toàn cục. Nếu `my_dataset` lớn hơn quota
train 70%, audit phải `BLOCKED`; không được tự ý phá tỷ lệ hoặc đưa một phần
`my_dataset` sang val/test.

Split phải group-aware theo source/video/sequence. Không được có một trong các
loại overlap sau giữa train, val và test:

- Cùng file ảnh.
- Cùng SHA-256 image hash.
- Cùng frame sequence hoặc video group.
- Cùng bản sao đã đổi tên.

Nếu group-aware split làm actual ratio lệch nhẹ, `split_registry.json` phải ghi
target count, actual count, phần trăm thực tế, sai lệch và group đã gây lệch.

## Runtime outputs

```text
.runtime/datasets/drone-single-class/
├── data.yaml
├── audit.json
├── manifest.json
├── split_registry.json
└── label_statistics.json
```

Training chỉ được chạy khi `audit.json` có `status: valid` và split registry đã
được kiểm tra không overlap.

