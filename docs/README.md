# Tài liệu dự án

Tài liệu được chia theo mục đích sử dụng để dễ tìm và tránh trộn kế hoạch với kết quả thực thi:

- [`plan/`](plan/) — nghiên cứu, kế hoạch triển khai và phase runbook.
- [`report/`](report/) — báo cáo kiểm thử, benchmark, audit, kết quả thực thi và evidence; các báo cáo tracking được giữ theo từng scope trong [`report/tracking/`](report/tracking/).
- [`description/`](description/) — mô tả kiến trúc, dataset, training, layout repository và hướng dẫn bàn giao.

## Quy ước

- Tài liệu mới phải đặt đúng nhóm ngay khi tạo.
- `plan/` trả lời dự án sẽ làm gì và làm theo thứ tự nào.
- `report/` trả lời đã làm gì, kết quả ra sao và có bằng chứng nào.
- `description/` trả lời hệ thống được tổ chức và vận hành như thế nào.

## Lối vào nhanh

- Kế hoạch tổng thể: [`plan/RESEARCH_PLAN.md`](plan/RESEARCH_PLAN.md)
- Runbook theo phase: [`plan/phases/README.md`](plan/phases/README.md)
- Báo cáo trạng thái Pi: [`report/PI5_EXECUTION_STATUS.md`](report/PI5_EXECUTION_STATUS.md)
- Mô tả cấu trúc repository: [`description/REPOSITORY_LAYOUT.md`](description/REPOSITORY_LAYOUT.md)
# Anti-drone project documentation

The existing project structure is preserved. All new documentation must be stored
under `docs/` and organized into these sections:

- `docs/description/`: project descriptions, folder layout, dataset notes, and handoff material.
- `docs/report/`: execution reports, status updates, test results, and evaluations.
- `docs/plan/`: plans, training strategy, deployment plans, and research plans.

Use English for filenames and content so the documentation stays consistent across
Windows, Linux, the server, and Pi 5.
