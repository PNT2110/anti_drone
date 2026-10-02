# Scope 17 — Label Repair Audit

Independent direct-disk audit: `scripts/audit_scope17_labelrepair.py`, kết quả **PASS** trước khi tạo `data.yaml`.

- Samples: 30.227; train/val/test: 12.142 / 8.237 / 9.848.
- Source-confirmed objects: 30.227.
- Source-confirmed negatives: 0.
- Source annotation unresolved: 0.
- Output objects: 30.227; mỗi frame đúng một object.
- Trước repair: 4.700 labeled images, 25.527 empty images.
- Sau repair: 30.227 labeled images, 0 negative images.
- Repair status: `REPAIRED_FROM_SOURCE_ANNOTATION=30.227`.
- Image content/hash khớp V3 candidate gốc: PASS.
- Source-sequence overlap: 0; candidate-prefix overlap: 0.
- Quarantine leakage: 0.
- Class/bbox/coordinate tolerance: PASS.
- `data.yaml` chỉ xuất hiện sau audit PASS.

Repair manifest hash: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`.

Dataset repair candidate đạt `LABEL_READY` trong phạm vi Scope 17, nhưng vẫn là candidate-only; chưa phải production, chưa chứng minh session independence.
