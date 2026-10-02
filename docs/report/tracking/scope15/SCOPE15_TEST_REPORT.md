# Scope 15 Test Report

Các kiểm tra Scope 15 đã chạy:

1. `python scripts/scope15_input_audit.py` — PASS.
2. `python scripts/materialize_scope15_v3_candidate.py` — PASS; physical copy hoàn tất.
3. `python scripts/audit_scope15_v3_candidate.py` — PASS.
4. `python scripts/finalize_scope15_v3_candidate.py` — PASS; chỉ sau direct audit mới tạo `data.yaml` và sáu config.
5. `/home/pnt/miniconda3/envs/antidrone/bin/python scripts/scope15_loader_smoke.py` — PASS.
6. `python -m pytest -q` — **80 passed, 1 skipped**.
7. `python -m compileall -q scripts src tests` — **PASS**.
8. `git diff --check` — **PASS**.

Không chạy train, epoch, validation chọn model, test scoring, tracker, Pi hoặc camera live.
