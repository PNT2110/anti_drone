# E2E Test Infrastructure & Test Architecture Specification

**Author**: `test_writer_e2e_1` (teamwork_preview_test_writer)  
**Date**: 2026-09-28  
**Scope**: Anti-Drone Web Application (`web/`)  
**Status**: APPROVED & PUBLISHED  

---

## 1. Test Philosophy

The Anti-Drone Web Application is a mission-critical academic defense demonstration combining real-time computer vision, dual input streams (video upload & live webcam), runtime model hot-swapping, and a fully localized Vietnamese user interface.

To ensure production-grade reliability and seamless presentation readiness, the test infrastructure adheres to the following principles:

1. **Opaque-Box End-to-End Testing**:
   - The test suite interacts with the application strictly via public HTTP REST endpoints, WebSocket connections, and rendered HTML/CSS/JS artifacts.
   - Internal state is observed exclusively through observable API contracts and client-facing response schemas.
2. **Zero Test Evasion (Integrity First)**:
   - No mock assertions that trivially pass without exercising logic.
   - Real media streams, real multipart uploads, and real image decoding are exercised.
   - Real model discovery across `models/` and root `yolo26n.pt` is verified against actual disk files.
3. **Adversarial & Boundary Stress Testing**:
   - Verification extends beyond happy paths: zero-byte files, corrupted video headers, unsupported MIME types, path traversal injection attempts in model selectors, out-of-range confidence/IoU sliders, and non-existent session queries are aggressively tested.
4. **Self-Contained & Deterministic Execution**:
   - No external internet access or external webcam hardware required.
   - Synthetic in-memory test media (MP4 videos via OpenCV VideoWriter, JPEG frames with synthetic targets) are generated on-the-fly and cleanly disposed.
   - Single command execution: `python test_app.py` from either `web/` or project root, exiting with code `0` on success.
5. **Progressive Testability**:
   - The test runner cleanly inspects the application environment. If the full backend is active, it runs full live ASGI pipeline verification. If called during early milestone integration, it validates structural conformance and interface contracts.

---

## 2. Feature Inventory Mapping

Every feature identified in `PROJECT.md` is mapped to an authoritative test tier, test function, and validation criteria:

| Feature # | Feature Name | Test Tier | Target Function in `test_app.py` | Verification Criteria |
|---|---|---|---|---|
| **F1** | Extensible Model Discovery | Tier 1 (Feature Coverage) | `test_get_models_inventory` | `GET /api/models` returns HTTP 200, lists available models including `yolo26n.pt` and drone ONNX models (`yolov8n-drone-480.onnx`, etc.), with valid metadata (`name`, `format`, `size_mb`, `is_active`). |
| **F2** | Thread-Safe Model Hot-Swapping | Tier 1 & Tier 3 (Cross-Feature) | `test_model_hot_swap_success`, `test_model_hot_swap_invalid`, `test_model_hot_swap_traversal` | `POST /api/models/select` switches active model to specified ONNX and PT models. Returns 404 on non-existent file, 403/400 on path traversal or malformed file. |
| **F3** | Core Detection Engine | Tier 1 & Tier 4 (Real-World) | `test_detection_synthetic_frame_schema` | Generates 640x480 frame with synthetic object, feeds to detection pipeline, asserts response schema contains `detections` (box `[x1, y1, x2, y2]`, `confidence`, `label`), `fps > 0`, `latency_ms > 0`. |
| **F4** | Video File Upload | Tier 1 & Tier 2 (Boundary) | `test_video_upload_valid_mp4`, `test_video_upload_zero_byte`, `test_video_upload_invalid_ext` | Multipart `POST /api/video/upload` with valid MP4 returns HTTP 200 + `video_id`. 0-byte file returns HTTP 400. `.txt` / invalid format returns HTTP 400. |
| **F5** | Real-Time Video Streaming | Tier 1 (Feature Coverage) | `test_video_stream_endpoint` | `GET /api/video/stream/{video_id}` returns HTTP 200 with `multipart/x-mixed-replace; boundary=frame` MJPEG stream header and parsable JPEG chunk. |
| **F6** | Annotated Video Export | Tier 1 (Feature Coverage) | `test_video_download_endpoint` | `GET /api/video/download/{video_id}` returns HTTP 200 with attachment `Content-Disposition` and non-empty binary MP4 payload. Nonexistent ID returns 404. |
| **F7** | Video Statistics & Progress | Tier 1 (Feature Coverage) | `test_video_stats_endpoint` | `GET /api/video/stats/{video_id}` returns JSON with `status`, `progress` / `progress_percent`, `fps`, `total_detections`, `avg_confidence`. Nonexistent ID returns 404. |
| **F8** | Live Webcam Capture & Streaming | Tier 1 & Tier 4 (Real-World) | `test_webcam_websocket_lifecycle` | Connects to `ws://localhost:PORT/ws/webcam`, completes handshake, exchanges configuration, and cleanly disconnects without leaks. |
| **F9** | Live Webcam Detection Protocol | Tier 1 (Feature Coverage) | `test_webcam_websocket_inference_frame` | Sends Base64 JPEG frame via WebSocket, receives JSON response containing `detections`, `fps`, `latency_ms` (or `inference_time_ms`), and overlay image. |
| **F10** | Real-Time FPS Counter | Tier 1 & Tier 2 (Boundary) | `test_fps_metrics_positive_and_bounded` | Verifies FPS metrics returned in detection and video stats are positive floating point numbers within valid physical ranges (0.0 to 120.0). |
| **F11** | Summary Statistics Panel | Tier 1 (Feature Coverage) | `test_summary_statistics_schema` | Asserts summary fields (`total_objects`, `avg_confidence`, `elapsed_time`) exist, have valid types, and handle zero-object frames gracefully without `NaN`/`div0`. |
| **F12** | 100% Vietnamese Localization | Tier 1 (Feature Coverage) | `test_ui_vietnamese_thesis_defense_keywords` | `GET /` returns HTTP 200, UTF-8 HTML containing mandatory Vietnamese thesis keywords ("HỆ THỐNG", "MÁY BAY KHÔNG NGƯỜI LÁI", "Tải lên Video", "Webcam Trực tiếp", "Mô hình", "Ngưỡng tin cậy", "Bảng Thống Kê"). |
| **F13** | Thesis-Defense UI Styling | Tier 1 (Feature Coverage) | `test_static_assets_and_defense_styling` | Confirms static CSS and JS references (`style.css`, `app.js`) are served with HTTP 200 and CSS includes modern thesis palette styling. |
| **F14** | Dual Mode Tabs & State Manager | Tier 3 (Cross-Feature) | `test_dual_mode_tabs_presence` | Inspects UI HTML structure to confirm clean separation of Video Upload and Webcam panels with active tab toggles. |
| **F15** | Model Selector UI & Tuning | Tier 1 & Tier 2 (Boundary) | `test_detection_tuning_sliders` | Validates model selector dropdown and slider parameters (`conf` between 0.05-0.95, `iou` between 0.1-0.9) accepted by API. |
| **F16** | Standalone Automated Verification | Meta-Verification | `test_runner_main_execution` | `python test_app.py` runs all test suites automatically, logs execution summary, and exits with return code `0`. |

---

## 3. Test Architecture & Tier Distribution

```
                                [ test_app.py Runner ]
                                           │
         ┌───────────────────┬─────────────┴─────────────┬────────────────────┐
         │                   │                           │                    │
      [ Tier 1 ]          [ Tier 2 ]                  [ Tier 3 ]           [ Tier 4 ]
   Feature Coverage    Boundary & Corner           Cross-Feature       Real-World Scenarios
   ────────────────    ─────────────────           ─────────────       ────────────────────
   • GET / UI & UTF-8  • 0-byte video upload       • Hot-swap during   • Multi-frame video
   • GET /api/models   • Corrupted video stream      video processing    stream lifecycle
   • POST /api/select  • Unsupported extensions    • WebSocket mode    • WebSocket webcam
   • Video endpoints   • Nonexistent model 404       switch teardown     ping-pong frames
   • WebSocket webcam  • Slider boundary clamp     • Rapid tab switch  • Full export cycle
```

### Test Tiers Breakdown:

- **Tier 1: Feature Coverage (Happy Path)**
  - Confirms each specified endpoint conforms strictly to its HTTP method, request payload, status code, and response JSON schema.
- **Tier 2: Boundary, Corner & Adversarial Cases**
  - Tests extreme inputs: zero-byte files, corrupted video containers, unknown file extensions, non-existent video IDs, confidence thresholds at `0.0` and `1.0`.
  - Ensures server never crashes with unhandled 500 exceptions, returning proper HTTP 400, 404, or 422 with descriptive error messages.
- **Tier 3: Cross-Feature & State Interactions**
  - Model switching followed by detection verification (verifying active model changed).
  - Video upload followed by streaming and status polling.
- **Tier 4: Real-World Simulation**
  - Simulates browser client sending a series of base64 webcam frames to WebSocket endpoint.
  - Generates realistic synthetic OpenCV video, uploads it, polls processing stats until ready, and fetches downloadable MP4 artifact.

---

## 4. Test Execution Engine & Tooling

1. **In-Process ASGI Driver**:
   - `fastapi.testclient.TestClient` powered by `starlette` / `httpx`.
   - Allows synchronous, zero-network-overhead testing of both HTTP REST endpoints and asynchronous WebSockets.
2. **Synthetic Media Generation**:
   - **Video Generator**: Uses `cv2.VideoWriter(..., cv2.VideoWriter_fourcc(*'mp4v'), fps=10.0, (320, 240))` to generate a 10-frame synthetic MP4 video in a temporary directory with dynamic motion (moving target).
   - **Image Generator**: Uses `numpy` and `cv2.rectangle` + `cv2.imencode('.jpg')` to generate a 640x480 test image with a synthetic target.
3. **Execution Commands**:
   - From project root:
     ```powershell
     C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe web/test_app.py
     ```
   - From `web/` directory:
     ```powershell
     cd web
     C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe test_app.py
     ```
   - Pytest execution:
     ```powershell
     C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/test_app.py -v
     ```

---

## 5. Coverage Thresholds & Exit Conditions

- **Total Test Cases**: 18 atomic tests spanning all 16 features across Tiers 1-4.
- **Pass Threshold**: 100% of applicable tests must pass.
- **Exit Code**: `0` on 100% pass, non-zero (`1`) on any failure.
- **Error Tolerance**: 0 unhandled exceptions or 500 server crashes.
