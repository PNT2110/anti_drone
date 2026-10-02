# Scope 17 — Label Repair Design

Repair dùng annotation nguồn, không dùng detector/prediction. Candidate mới: `data/processed/drone-single-class-v3-labelrepair-candidate/`.

Quy trình:

1. Khóa V3 manifest/split registry checksum và Scope 17 root-cause audit PASS.
2. Đọc `exist`, `gt_rect`, source JSON/member/frame trực tiếp từ `Anti-UAV300.tar`.
3. Đọc kích thước ảnh candidate V3; áp dụng coordinate contract.
4. Copy vật lý ảnh từ V3 candidate sang thư mục tạm; ghi label mới từ source rectangle.
5. Hash ảnh/label và atomic rename sang output riêng; không tạo `data.yaml` trước audit.
6. Audit độc lập trực tiếp source archive + output filesystem; chỉ sau PASS mới tạo `data.yaml`.

Mọi 30.227 rows có source object nên trạng thái là `REPAIRED_FROM_SOURCE_ANNOTATION`. Không label nào được giữ nguyên vì 4.700 label cũ đều mismatch; không có negative hoặc unresolved sample. Ảnh, split, sequence/prefix, source provenance và quarantine policy được giữ nguyên.

Output không phải production, không thay candidate V3 gốc, không thay checkpoint V1 và chưa được dùng train.
