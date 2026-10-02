# Scope 17 — Test Report

Đã chạy:

- Root-cause audit: **PASS**.
- Label-repair materialization: **PASS**.
- Independent label-repair audit: **PASS**.
- Loader smoke: **PASS**.
- `python -m pytest -q`: **85 passed, 1 skipped**.
- `python -m compileall -q scripts src tests`: **PASS**.
- `git diff --check`: **PASS**.

Regression guards Scope 17 kiểm tra frame 0-based, coordinate conversion, baseline hash, split/quarantine, repair counts và không khởi động Scope 16 training. Không train YOLO, không đọc V3 test để tuning, không thay V1/V2/checkpoint/tracker/Pi.
