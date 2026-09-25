# V3 Direct-Disk Audit

Audit độc lập: `scripts/audit_scope15_v3_candidate.py`, artifact `.runtime/scope15/direct_disk_audit.json`. Kết quả: **PASS** trước khi tạo `data.yaml`.

- Manifest/filesystem: 30,227 samples; counts train/val/test lần lượt 12,142 / 8,237 / 9,848.
- Quarantine leakage: 0; loại khỏi candidate là 6,505 samples / 4,172 groups.
- Source sequence: 318 sequence, overlap qua split: 0.
- Candidate prefix: 63 prefix, overlap qua split: 0.
- Group crossing split: 0; original train/val/test boundary: PASS.
- Exact source path overlap giữa các split: 0.
- Exact source hash overlap giữa các split: 0.
- Image/label output hash khớp source tương ứng: PASS.
- Label objects: 4,790; class ID 0, normalized bbox, kích thước dương và biên với epsilon `1e-6`: PASS.
- Symlink/hardlink risk: không phát hiện symlink; bản copy vật lý độc lập.
- Kiểm tra 60,454 cặp output/source theo `(device, inode)`: shared inode `0`.
- `SESSION_DISJOINT`: **UNVERIFIED**. Kết quả này không được nâng thành session-independent.

Hash audit: `f089d5229c0d09441c33fe57647004be7e64bad843d1b579b4234273bebca9cf`. Direct audit chứng minh source-sequence/prefix disjoint theo mapping; không chứng minh session thật độc lập.
