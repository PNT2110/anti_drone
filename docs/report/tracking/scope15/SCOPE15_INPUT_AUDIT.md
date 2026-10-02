# Scope 15 — Input Audit

Ngày thực hiện: 2026-09-22. Repository: `/run/media/pnt/APP/anti_drone`.

Baseline được khóa trước khi materialize bằng `scripts/scope15_input_audit.py`; kết quả: **PASS**. Branch là `main`, HEAD là `5996f69 Add repository pipeline and architecture guide`. Các thay đổi Git có sẵn được giữ nguyên; Scope 15 không commit/push.

Các checksum baseline được lưu đầy đủ tại `.runtime/scope15/input_baseline.json`, gồm V1 manifest/split registry, V2 manifest/registry/audit, executable V2 manifest/data.yaml, Scope 13 mapping, Scope 14 conservative CSV/audit và V1 checkpoint. Các checksum thực tế khớp baseline đã nghiệm thu:

- V1 manifest: `3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d`.
- V2 manifest: `9605532a2b24566b691554125074c37f198c452bce343883b2a6720847299aa1`.
- Executable V2 manifest: `c66e201aae060b96687c841d54a3297a1ea9fe7788d9101521bffe87f43db9aa`.
- Scope 13 mapping: `ffb0d14247ff02f9d30e14011769435fd296103e4fe735e02abbb30cd1396d4e`.
- Scope 14 conservative CSV: `eb045f9d0c9f6f247e092b3b8c45389d80a495c7a26e2f8523554dd89b6afa57`.
- V1 checkpoint: `662fbc1c066041345970f4211a6ceb9209907a331fd1724c0b2be7e53a4beec1`.

Scope 14 Option B được dùng đúng như thiết kế: original Anti-UAV300 `train → train`, `val → val`, `test → test`; sequence và candidate date/time prefix là atomic. Counts kỳ vọng là `12,142 / 8,237 / 9,848`; 6,505 samples và 4,172 groups quarantine tiếp tục bị loại.

Không có training, validation model, tracker/gate, Pi/camera live hay thay đổi checkpoint V1.
