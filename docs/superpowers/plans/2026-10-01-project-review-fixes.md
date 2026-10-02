# Project Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sửa các vấn đề tìm được trong lần rà soát ngày 2026-10-01: web app không xác thực, upload không giới hạn, tác vụ video treo, test/CI không kiểm tra code thật, repo git chứa dataset và rác runtime, tài liệu sai.

**Architecture:** Giữ nguyên cấu trúc `web/app.py` + `web/backend/`. Thêm một module nhỏ `web/security.py` cho xác thực (HTTP Basic + cookie phiên cho WebSocket). Các sửa còn lại là thay đổi tại chỗ. Test mới chạy trên app thật với `manager` giả, không cần `ultralytics`/GPU.

**Tech Stack:** Python 3.12, FastAPI, OpenCV, pytest, GitHub Actions.

**Spec:** Báo cáo rà soát trong phiên làm việc 2026-10-01 (17 mục). Không có file spec riêng; bảng "Ánh xạ" bên dưới là nguồn đối chiếu.

## Global Constraints

- Không sửa, di chuyển hay xoá file trong `data/` trên đĩa. Chỉ gỡ khỏi git index.
- Không viết lại lịch sử git, không force-push, không commit. Thay đổi để ở working tree/index cho người dùng duyệt.
- Không đổi hành vi tracker (`IdentityTracker.update`); 11 test tracker hiện có phải tiếp tục pass.
- Mọi cấu hình mới đọc từ biến môi trường tiền tố `ANTI_DRONE_`.
- Thông báo lỗi hiển thị cho người dùng viết bằng tiếng Việt.

## Ánh xạ mục rà soát → task

| Mục | Nội dung | Task |
|---|---|---|
| 1 | Dataset/rác trong git, không có `.gitignore` | 8 |
| 2 | `main` và `origin/main` không chung lịch sử | Không tự làm — cần người dùng quyết định |
| 3 | Không xác thực, mở tunnel công khai | 1, 7 |
| 4 | Upload không giới hạn | 2 |
| 5 | `stop.bat` giết mọi python.exe | 7 |
| 6 | Tác vụ video treo khi lỗi | 3 |
| 7 | Đổi model lỗi vẫn báo thành công | 4, 6 |
| 8 | `/ws/webcam` chặn event loop | 4 |
| 9 | Race ở `seen_ids` | 3 |
| 10 | Hai bộ tham số tracker | 5 |
| 11 | `evaluate_tracker_grid.py` sai đường dẫn | 9 |
| 12 | XSS qua `innerHTML` | 6 |
| 13 | `test_app.py` test app giả | 1–4 (test mới), 10 |
| 14 | CI không kiểm tra gì | 10 |
| 15 | README sai | 10 |
| 16 | Đường dẫn cứng | 9 |
| 17 | `KNOWN_MODELS_METADATA` chết | Giữ nguyên — `test_model_engine.py:106-112` đang assert các khoá này |

## Review Focus

1. Mật khẩu đặt rồi nhưng trình duyệt mở WebSocket không gửi header `Authorization` → vẫn phải vào được nhờ cookie phiên (test ở Task 1).
2. Upload đúng đuôi `.mp4` nhưng nội dung không phải video → task chuyển sang `error`, không treo ở `processing` (test ở Task 3).
3. Upload vượt giới hạn giữa chừng → trả 413 và không để lại file dở trong `web/tmp/` (test ở Task 2).
4. Gọi `/api/video/stats` liên tục trong lúc thread đang ghi → không văng exception (test ở Task 3).
5. `ModelManager` khởi tạo lỗi (`manager is None`) → mọi endpoint suy luận trả 503 thay vì 500 (test ở Task 4).

---

### Task 1: Xác thực

**Files:**
- Create: `web/security.py`
- Modify: `web/app.py`
- Test: `web/tests/conftest.py` (mới), `web/tests/test_app_api.py` (mới)

**Interfaces — Produces:**
- `security.get_password() -> str | None` — đọc `ANTI_DRONE_PASSWORD`, chuỗi rỗng coi như không đặt.
- `security.BasicAuthMiddleware` — ASGI middleware. Không đặt mật khẩu: cho qua. Có mật khẩu: scope `http` cần Basic đúng (user bất kỳ) hoặc cookie `anti_drone_session` đúng, sai thì 401 kèm `WWW-Authenticate: Basic`; khi qua bằng Basic thì set cookie `HttpOnly; SameSite=Strict`. Scope `websocket` sai thì đóng với code 1008.
- `security.is_loopback(host: str) -> bool`.
- `conftest.py` cung cấp fixture `client` (TestClient trên `app.app` thật, `app.manager` thay bằng `FakeManager`, `app.TMP_DIR` trỏ `tmp_path`) và `FakeManager` có `predict`, `list_models`, `set_active_model`.
- So sánh mật khẩu bằng `hmac.compare_digest`. Giá trị cookie là HMAC-SHA256 của mật khẩu với khoá ngẫu nhiên sinh mỗi lần khởi động.

- [ ] **Step 1: Viết test (fail)** — `test_no_password_allows_access`, `test_password_blocks_anonymous` (401 + header), `test_password_accepts_basic_and_sets_cookie`, `test_wrong_password_rejected`, `test_websocket_rejected_without_credentials`, `test_websocket_accepted_with_session_cookie`.
- [ ] **Step 2: Chạy** `python -m pytest web/tests/test_app_api.py -q` → FAIL.
- [ ] **Step 3: Viết `web/security.py`, gắn middleware trong `app.py`.**
- [ ] **Step 4: `__main__` của `app.py`:** host/port lấy từ `ANTI_DRONE_HOST` (mặc định `127.0.0.1`) và `ANTI_DRONE_PORT`; nếu host không phải loopback mà chưa đặt mật khẩu thì `SystemExit` kèm hướng dẫn.
- [ ] **Step 5: Chạy lại** → PASS.

### Task 2: Giới hạn upload

**Files:** Modify `web/app.py`; Test `web/tests/test_app_api.py`

**Quyết định:**
- Đuôi file phải thuộc `SUPPORTED_VIDEO_EXTENSIONS` → sai trả 400.
- Ghi xuống đĩa theo khối 1 MB; vượt `MAX_UPLOAD_SIZE_BYTES` trả 413 và xoá file dở; 0 byte trả 400.
- Số tác vụ `queued`/`processing` đồng thời tối đa `ANTI_DRONE_MAX_VIDEO_TASKS` (mặc định 2) → vượt trả 429.
- `task_id = uuid.uuid4().hex` (32 ký tự).
- Trước mỗi upload gọi `prune_video_tasks()`: xoá task đã kết thúc quá `ANTI_DRONE_VIDEO_TTL_SECONDS` (mặc định 3600) và các file `*_in.mp4`/`*_out.mp4` trong `TMP_DIR` có mtime cũ hơn TTL mà không thuộc task đang chạy.

- [ ] **Step 1: Test** — `test_upload_rejects_unsupported_extension` (400), `test_upload_rejects_empty_file` (400), `test_upload_rejects_oversize_and_cleans_up` (413, `TMP_DIR` rỗng), `test_upload_rejects_when_too_many_tasks` (429), `test_prune_removes_expired_task_and_files`.
- [ ] **Step 2: Chạy → FAIL. Step 3: Cài đặt. Step 4: Chạy → PASS.**

### Task 3: Tác vụ video không treo, không race

**Files:** Modify `web/app.py`; Test `web/tests/test_app_api.py`

**Quyết định:**
- `video_tasks` được bảo vệ bằng `video_tasks_lock = threading.Lock()`; `video_stats` chụp bản sao dưới lock.
- `process_video_task` bọc `try/except/finally`: lỗi bất kỳ → `status='error'`, `message=<chuỗi lỗi>`; `finally` luôn `release()` và ghi `finished_at`.
- `VideoWriter` không mở được, hoặc `manager is None` → lỗi như trên.
- Stream MJPEG thoát khi status là `completed` hoặc `error`.
- `stats`/`stream` với id lạ trả 404.

- [ ] **Step 1: Test** — `test_invalid_video_content_ends_in_error_status`, `test_predict_exception_ends_in_error_status`, `test_valid_video_completes_and_is_downloadable`, `test_stats_unknown_task_returns_404`, `test_stats_is_safe_during_processing`.
- [ ] **Step 2–4: FAIL → cài đặt → PASS.**

### Task 4: Endpoint model và suy luận

**Files:** Modify `web/app.py`; Test `web/tests/test_app_api.py`

**Quyết định:**
- `manager is None` → `/api/detect`, `/api/models/switch`, `/api/video/upload` trả 503; hai WebSocket gửi `{"error": ...}` rồi đóng 1011.
- `/api/models/switch`: `KeyError` (lớp cha của `ModelNotFoundError`) → 404; lỗi khác → 500; chạy `set_active_model` qua `asyncio.to_thread`.
- `/api/detect` và `/ws/webcam` gọi `manager.predict` qua `asyncio.to_thread`. Frame webcam hỏng (base64/JPEG sai) thì bỏ qua, không đóng kết nối.

- [ ] **Step 1: Test** — `test_switch_unknown_model_returns_404`, `test_switch_success`, `test_endpoints_return_503_without_manager`, `test_detect_returns_detections`, `test_webcam_skips_malformed_frame`.
- [ ] **Step 2–4: FAIL → cài đặt → PASS.**

### Task 5: Một bộ tham số tracker

**Files:** Modify `web/backend/tracker.py`, `web/backend/detector.py`, `web/app.py`; Test `web/tests/test_tracker_long_term_reid.py`

**Interfaces — Produces:** `tracker.create_tracker_from_env() -> IdentityTracker`, mặc định: TTL 4.0, memory 60.0, threshold 0.45, min-new 0.25, gallery 0.15 (bộ đã tinh chỉnh ở `app.py`).

- `detector.py` và `app.create_stream_tracker` đều gọi hàm này.
- `/api/detect` truyền tracker mới cho mỗi request để ID không lẫn giữa các ảnh.

- [ ] **Step 1: Test** `test_env_factory_defaults_and_overrides`. **Step 2–4: FAIL → cài đặt → PASS (12 test).**

### Task 6: Frontend

**Files:** Modify `web/static/js/app.js`

- `notify()` dựng DOM bằng `textContent`, không dùng `innerHTML` với dữ liệu ngoài.
- Đổi model: khi `!response.ok` hiện `message` từ JSON và chọn lại model cũ.
- `updateVideoStats`: `!response.ok` → dừng polling, báo lỗi.
- Lỗi upload hiện `error` từ JSON (413/429/400).

- [ ] **Step 1: Sửa. Step 2:** `node --check web/static/js/app.js` nếu có node.

### Task 7: Script khởi động/dừng

**Files:** Modify `web/start.bat`, `web/stop.bat`, `web/app.py`

- `app.py` khi chạy `__main__` ghi PID vào `web/server.pid`, xoá khi thoát.
- `stop.bat` đọc `server.pid` và `taskkill /PID`; không còn `/im python.exe`.
- `start.bat` từ chối chạy nếu chưa đặt `ANTI_DRONE_PASSWORD`; bỏ dòng "Mat khau truy cap: 1234".

### Task 8: Vệ sinh git

**Files:** Create `.gitignore`; gỡ khỏi index (giữ trên đĩa)

- Ignore: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.log`, `web/tmp/`, `web/outputs/`, `web/server.pid`, `data/**` trừ `data/**/data.yaml` và `.gitkeep`, `artifacts/video_tests/`, `artifacts/**/*.tar.gz`, `artifacts/**/*.tgz`, `artifacts/models/**/*.pt` (giữ `results.csv`, `args.yaml`, manifest vì nhỏ và có giá trị đối chiếu), `.venv/`.
- `git rm -r --cached` các đường dẫn trên.
- Giữ theo dõi: `models/`, `web/models/`, `artifacts/deploy*`, `artifacts/releases`, `artifacts/production-candidate` (đều < 100 MB/file).

- [ ] **Verify:** `git ls-files | wc -l` < 1000; không còn file > 100 MB trong index.

### Task 9: Script và đường dẫn

**Files:** Modify `scripts/evaluate_tracker_grid.py`, `scripts/evaluate_fresh_models_on_videos.py`, `data/data_train/data.yaml`

- `evaluate_tracker_grid.py`: tìm tracker ở `<repo>/web/backend/tracker.py`, dự phòng `<script dir>/backend/tracker.py` (bố cục phẳng trên server).
- `evaluate_fresh_models_on_videos.py`: thêm `--indoor`, `--outdoor` (mặc định giữ `/tmp/...`); không mở được video thì `SystemExit`.
- `data.yaml`: bỏ dòng `path:` tuyệt đối để Ultralytics dùng thư mục chứa file yaml.

### Task 10: Test cũ, CI, README

**Files:** Delete `web/test_app.py`; Modify `.github/workflows/ci.yml`, `README.md`, `web/requirements.txt`

- Xoá `web/test_app.py` (test trên app giả, sai hợp đồng API); `test_app_api.py` thay thế.
- CI: Python 3.12, cài `fastapi httpx python-multipart jinja2 opencv-python-headless numpy pytest`, chạy `python -m compileall -q web scripts` và `pytest web/tests/test_tracker_long_term_reid.py web/tests/test_app_api.py`.
- README: viết lại theo đúng cây thư mục và lệnh thật; thêm mục biến môi trường và bảo mật.

- [ ] **Verify cuối:** `python -m pytest web/tests/test_tracker_long_term_reid.py web/tests/test_app_api.py -q` → tất cả PASS.
