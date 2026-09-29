# Specification Mining & Requirement Analysis Report: Web-based Object Detection Demo

**Agent ID**: `spec_miner_survey_1`  
**Working Directory**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\.agents\teamwork\spec_miner_survey_1\`  
**Target Application Root**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\web`  
**Date**: 2026-09-28  

---

## 1. Observation

Direct empirical observations gathered from authoritative specification sources, environment probes, and codebase inspection:

### 1.1 Requirements Source (`ORIGINAL_REQUEST.md`)
- **Target Application**: Web-based object detection demo for university thesis defense presentation. Runs locally on Windows, uses YOLO models via Ultralytics, supports uploaded video files and live laptop webcam feed.
- **UI Localization**: Entirely in Vietnamese (`R3`).
- **Initial Model**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\yolo26n.pt` (YOLO26n pretrained on COCO, 80 classes, 5.3 MB). Architecture must allow drop-in swapping of custom single-class drone models (`R4`).
- **Target Working Directory**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\web`.
- **Target Python Environment**: `C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe`.

### 1.2 Environment & Package Probing Results
Executing Python 3.12 runtime inspection confirmed:
- `Python`: `3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]`
- `ultralytics`: `8.4.121`
- `opencv-python`: `5.0.0`
- `torch`: `2.13.0+cpu` (`torch.cuda.is_available() == False`)
- `fastapi`: `0.141.1`
- `uvicorn`: `0.52.3`
- `websockets`: `16.1.1`
- `starlette`: `1.3.1`
- `python-multipart`: `0.0.32`
- `jinja2`: `3.1.6`
- `httpx`: `0.28.1`
- `requests`: `2.34.2`
- `pytest`: `9.1.1`
- `onnxruntime`: `1.29.0`
- `ncnn`: `1.0.20260526`
- Note: `flask` is **NOT installed**; `fastapi` and `uvicorn` are pre-installed and fully functional with WebSocket, multipart, and streaming support.

### 1.3 Model Loading & Inference Probing (`yolo26n.pt`)
- Model load time: `0.059` seconds (`YOLO('yolo26n.pt')`).
- Hot swap time: `0.173` seconds when switching/re-instantiating model.
- Model metadata: `task = 'detect'`, `80` classes (`names = {0: 'person', 1: 'bicycle', 2: 'car', ...}`).
- CPU Inference latency: ~`108ms - 169ms` per 640x640 frame (~`5.9 - 9.2 FPS`). Meets the functional acceptance threshold of `≥ 5 FPS`.
- Detection results API: `r = model(frame)[0]` yields `r.boxes` (with `r.boxes.xyxy`, `r.boxes.conf`, `r.boxes.cls`), `r.speed` (`preprocess`, `inference`, `postprocess`), and `r.plot()` returning an annotated `numpy.ndarray`.
- Nonexistent model load behavior: Raises `FileNotFoundError: [Errno 2] No such file or directory`.
- Corrupt `.pt` file behavior: Raises `TypeError` / `UnpicklingError`.

### 1.4 Video I/O & Codec Probing (OpenCV on Windows)
- Read capabilities: Successfully opens and reads `.mp4`, `.avi`, and `.mkv` files via `cv2.VideoCapture`.
- Write capabilities: Codec `mp4v` (`cv2.VideoWriter_fourcc(*'mp4v')`) creates valid `.mp4` video files without external ffmpeg dependencies.
- Corrupted / 0-byte video handling: `cv2.VideoCapture(corrupt_path).isOpened()` returns `False`.

---

## 2. Logic Chain

1. **Backend Framework Selection**:
   - `ORIGINAL_REQUEST.md` permits Flask or FastAPI.
   - Probing reveals `flask` is not installed, whereas `fastapi 0.141.1`, `uvicorn 0.52.3`, `websockets 16.1.1`, and `python-multipart 0.0.32` are installed globally.
   - FastAPI provides native async streaming (`StreamingResponse`), native WebSocket (`WebSocketEndpoint`), OpenAPI schema docs, and high-performance async concurrency.
   - *Conclusion*: FastAPI + Uvicorn is the optimal, pre-validated backend framework.

2. **Dual-Mode Streaming Architecture**:
   - **Video Upload Mode**: Video files (.mp4, .avi, .mkv) are uploaded via multipart form data (`POST /api/video/upload`). Processing is performed frame-by-frame. To stream visual feedback with zero client decoding latency, an MJPEG stream (`GET /api/video/stream/{video_id}`) via `multipart/x-mixed-replace; boundary=frame` feeds directly into standard HTML `<img>` tags. Concurrently, real-time statistics (FPS, object count, confidence, progress) are polled via `GET /api/video/stats/{video_id}` or streamed via Server-Sent Events (SSE).
   - Concurrently, an annotated `.mp4` video is rendered using OpenCV `VideoWriter('mp4v')` and saved to `web/outputs/{video_id}.mp4` for download via `GET /api/video/download/{video_id}` (`R2`).
   - **Live Webcam Mode**: In browser, `navigator.mediaDevices.getUserMedia({ video: true })` captures the client laptop camera. Frames are captured on an HTML5 `<canvas>` and transmitted to the server via WebSocket (`ws://localhost:PORT/ws/webcam`). The server runs YOLO inference, generates bounding box overlays and metadata, and returns either an annotated JPEG base64 payload or structured bounding box coordinates with real-time stats (`R1`).
   - To prevent queue buildup when camera capture rate (30 FPS) exceeds CPU inference speed (~6 FPS), client transmission must follow a ping-pong / request-response loop (send next frame only after receiving prior response) with an optional server-side single-element frame drop queue.

3. **Model Extensibility & Hot-Swapping (`R4`)**:
   - The directory `web/models/` will house `.pt` models (and optionally `.onnx` / `.ncnn`).
   - On startup, if `web/models/yolo26n.pt` is missing, the backend checks for root `../yolo26n.pt` and copies/links it into `web/models/`.
   - The endpoint `GET /api/models` dynamically scans `web/models/` for all `.pt` files.
   - The endpoint `POST /api/models/select` performs atomic, thread-safe model swapping using `threading.Lock`. If an invalid or corrupted file is selected, the server safely reverts to the previous model and returns an informative HTTP 400 error.

4. **Thesis-Grade Vietnamese UI Localization (`R3`)**:
   - All headers, mode tabs, control buttons, status indicators, statistics cards, and error toasts must be strictly in Vietnamese.
   - Layout should feature an anti-drone theme (navy/dark blue header, clean cards, real-time dashboard grid) suitable for an academic defense.

---

## 3. Caveats

1. **GPU Acceleration**: CUDA is currently unavailable in the global Python environment (`torch.cuda.is_available() == False`). Inference runs on CPU. YOLO26n CPU latency is ~160ms (~6.2 FPS), which satisfies the `≥ 5 FPS` requirement, but models larger than nano (e.g. YOLOv8m/l/x) would be sluggish on CPU.
2. **Browser Media Permissions**: In non-localhost environments, browsers restrict `navigator.mediaDevices.getUserMedia` to HTTPS. Since the application runs locally (`http://localhost:PORT`), browser security allows webcam access, but explicit user permission is still required.
3. **OpenCV Codec Fallbacks**: `libopenh264` is missing on this Windows system, so `avc1` falls back to `mp4v`. `mp4v` produces standard MPEG-4 Part 14 containers playable across common video players and browsers.
4. **Existing Pi Runtime**: The repository contains `src/anti_drone/runtime.py` designed for Raspberry Pi 5. The new `web/` application is an independent Windows-based demo service as specified in `ORIGINAL_REQUEST.md`, but its design aligns with the broader project's detection pipeline.

---

## 4. Conclusion

All functional, technical, and architectural requirements in `ORIGINAL_REQUEST.md` have been fully investigated and verified against the actual Windows environment:
- The tech stack is verified: Python 3.12, FastAPI, Uvicorn, Ultralytics 8.4.121, OpenCV 5.0.0.
- All core requirements (R1 dual input, R2 visualization & export, R3 Vietnamese UI, R4 hot-swapping) are fully specified below with deterministic schemas, error codes, and edge-case behaviors.
- The system can be validated through `python test_app.py` without external dependencies.

---

## 5. Verification Method

To verify the specifications and environment readiness independently:
1. **Environment Verification**:
   ```powershell
   & "C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe" -c "import fastapi, uvicorn, ultralytics, cv2; print('All core libraries verified')"
   ```
2. **Model Integrity**:
   ```powershell
   & "C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe" -c "from ultralytics import YOLO; m = YOLO('yolo26n.pt'); print('Model OK, classes:', len(m.names))"
   ```
3. **Application Verification Script Contract (`test_app.py`)**:
   - Must run in `web/` directory: `python test_app.py`
   - Must start server, execute health check, list models, upload synthetic test frame/video, test model switching, verify detection response schema, and exit with code `0`.

---

## 6. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | R1: Video Upload | Video File Upload | Accepts video file (.mp4, .avi, .mkv), validates headers, stores in temporary session directory. | `file: UploadFile` (multipart/form-data) | `{"video_id": "uuid", "filename": "...", "total_frames": N, "fps": F, "width": W, "height": H}` | HTTP 400 for unsupported extension; HTTP 422 for 0-byte or corrupted file. | ORIGINAL_REQUEST.md R1 |
| 2 | R1: Video Upload | Real-Time Video Stream | Streams annotated frames frame-by-frame using MJPEG multipart replacement. | `video_id: str`, `conf: float`, `iou: float` | `multipart/x-mixed-replace; boundary=frame` stream of JPEG frames | HTTP 404 if video_id not found; terminates stream cleanly on EOF. | ORIGINAL_REQUEST.md R1 |
| 3 | R1: Video Upload | Video Processing Control | Allows pausing, resuming, or stopping the background video inference worker. | `video_id: str`, `action: "pause" \| "resume" \| "stop"` | `{"status": "ok", "state": "paused" \| "processing" \| "stopped"}` | HTTP 404 if invalid session; HTTP 400 if invalid action. | Probed Video Workflow |
| 4 | R1: Live Webcam | Webcam Video Capture | Web browser captures laptop camera feed using WebRTC `navigator.mediaDevices.getUserMedia`. | Browser device stream `video: true` | HTML5 `<video>` / `<canvas>` frame stream | JavaScript alert/toast if permission denied or camera not found. | ORIGINAL_REQUEST.md R1 |
| 5 | R1: Live Webcam | WebSocket Frame Inference | High-speed bidirectional WebSocket streaming camera frames to backend and returning annotations + stats. | Binary JPEG or JSON `{"image": "data:image/jpeg;base64,...", "timestamp": float}` | JSON `{"image": "data:image/jpeg;base64,...", "fps": float, "latency_ms": float, "detections": [...]}` | Graceful reconnect prompt if socket closes; dropped frame counter if buffer overflows. | ORIGINAL_REQUEST.md R1 |
| 6 | R2: Visualization | Bounding Box Overlay | Renders colored bounding boxes around detected objects directly onto frames or canvas. | Frame ndarray + detected `xyxy` coordinates + class name | Rendered rectangle with thickness 2, color coded by class | Bounding box clipped to frame boundary `[0, width]` and `[0, height]`. | ORIGINAL_REQUEST.md R2 |
| 7 | R2: Visualization | Confidence Score Label | Draws text label showing class name and confidence score (e.g. `drone 0.94` or `person 0.88`). | Box coordinates, class name string, confidence float | Text banner over or inside bounding box | Falls back to default font if OpenCV font fails; clamps label to top border. | ORIGINAL_REQUEST.md R2 |
| 8 | R2: Visualization | Real-Time FPS Counter | Computes and displays live frames-per-second indicator over video stream and dashboard. | Timestamps of current and previous N frames | Live FPS number (e.g., `18.5 FPS`) | Clamped to `0.0` if frames stall. | ORIGINAL_REQUEST.md R2 |
| 9 | R2: Statistics | Summary Statistics Panel | Real-time dashboard showing total detected objects, average confidence, per-frame latency, and cumulative count. | Per-frame detection array | JSON stats payload updated every frame / 500ms | Displays zero values cleanly if no detections; no `NaN` or `div0`. | ORIGINAL_REQUEST.md R2 |
| 10 | R2: Video Export | Annotated Video Download | Encodes processed frames into `.mp4` video using OpenCV `VideoWriter` and provides download link. | `video_id: str` | Binary `.mp4` file download (`Content-Disposition: attachment`) | HTTP 404 if processing not finished; HTTP 500 if file writer failed. | ORIGINAL_REQUEST.md R2 |
| 11 | R3: Localization | Vietnamese UI Presentation | All visual elements, labels, tooltips, dialogs, buttons, and error toasts localized in Vietnamese. | User locale / static HTML | Vietnamese HTML/CSS/JS interface | None (static localized template). | ORIGINAL_REQUEST.md R3 |
| 12 | R3: Localization | Mode Switcher & Tab View | Clean tabs separating "Tải lên Video" and "Webcam Trực Tiếp" with state preservation. | User click event | Active tab toggles display and halts inactive stream | Automatically stops webcam when switching to video mode to release camera. | ORIGINAL_REQUEST.md R3 |
| 13 | R4: Architecture | Dynamic Model Discovery | Scans `web/models/` directory for available `.pt` (and `.onnx`) models without requiring server restart. | File system listing of `web/models/` | JSON list of models: `[{"name": "...", "size_mb": 5.3, "active": bool}]` | Falls back to default `yolo26n.pt` if `models/` is empty or missing. | ORIGINAL_REQUEST.md R4 |
| 14 | R4: Architecture | Safe Model Hot-Swapping | Allows runtime model replacement via UI dropdown without restarting backend server. | `model_name: str` | `{"status": "ok", "active_model": "...", "classes": [...]}` | HTTP 404 if file missing; HTTP 400 if corrupted; maintains previous model on error. | ORIGINAL_REQUEST.md R4 |
| 15 | R4: Architecture | Detection Parameter Tuning | UI sliders for dynamically adjusting Confidence Threshold and NMS IoU Threshold. | `conf: float` (0.05-0.95), `iou: float` (0.1-0.9) | Parameter applied immediately to next inference frame | Clamped to valid range `[0.01, 1.0]`. | ORIGINAL_REQUEST.md R2/R4 |
| 16 | Verification | Automated Test Runner | Standalone test script `test_app.py` verifying full end-to-end pipeline automatically. | CLI command `python test_app.py` | Console log and process exit code `0` | Exits with non-zero code on test assertion failure. | ORIGINAL_REQUEST.md Acceptance |

---

## 7. Edge Cases & Boundary Conditions

| # | Feature | Input / Condition | Observed / Required Behavior |
|---|---------|-------------------|-----------------------------|
| 1 | Video Upload | Uploaded file with unsupported format (e.g. `.mov`, `.webm`, `.wmv`, `.pdf`) | Server returns HTTP 400 Bad Request with Vietnamese error message: `"Định dạng tệp không được hỗ trợ. Vui lòng tải lên tệp .mp4, .avi hoặc .mkv."`. |
| 2 | Video Upload | Corrupted video file (valid extension `.mp4` but corrupted byte headers) | `cv2.VideoCapture.isOpened()` returns `False`. Server returns HTTP 422 Unprocessable Entity: `"Tệp video bị hỏng hoặc không thể giải mã."`. |
| 3 | Video Upload | Zero-byte video file (0 bytes uploaded) | Server checks file size before processing; returns HTTP 400: `"Tệp video rỗng (0 bytes). Vui lòng chọn tệp hợp lệ."`. |
| 4 | Video Upload | Abrupt client disconnect during video processing | Server detects socket disconnection or polling timeout; cleanly releases `cv2.VideoCapture` and `cv2.VideoWriter` to prevent resource leaks. |
| 5 | Video Upload | Large video file (e.g. > 500 MB) | Streamed chunked upload to disk instead of loading full file into RAM; memory footprint remains constant (< 100 MB). |
| 6 | Live Webcam | User denies camera access in browser prompt | Browser raises `NotAllowedError`. UI catches exception and displays Vietnamese modal: `"Quyền truy cập camera bị từ chối. Vui lòng cho phép trình duyệt truy cập webcam và tải lại trang."`. |
| 7 | Live Webcam | Laptop camera already in use by another application (Zoom, Teams) | Browser raises `NotReadableError` / `TrackStartError`. UI displays: `"Không thể khởi động camera. Thiết bị có thể đang được ứng dụng khác sử dụng."`. |
| 8 | Live Webcam | Client camera produces 30 FPS while CPU inference runs at ~6 FPS | Client request-response loop: client awaits previous detection response before sending next frame. Server drops intermediate frames if queue > 1. Zero latency accumulation. |
| 9 | Live Webcam | Extreme network jitter or packet loss on WebSocket | Client monitors heartbeat; auto-reconnects with exponential backoff and informs user via toast: `"Đang kết nối lại máy chủ..."`. |
| 10 | Model Selector | `models/` directory does not exist on first launch | Server auto-creates `models/` directory; locates baseline `yolo26n.pt` from repository root and links or copies it into `models/`. |
| 11 | Model Selector | Nonexistent model requested via API (`POST /api/models/select`) | Server checks path existence; returns HTTP 404: `"Mô hình không tồn tại: <model_name>"`. Active model remains unchanged. |
| 12 | Model Selector | Malformed or corrupted `.pt` file placed in `models/` | Ultralytics raises `TypeError` / `UnpicklingError`. Server catches exception, logs traceback, keeps existing model active, and returns HTTP 400: `"Không thể tải mô hình: Tệp bị lỗi hoặc không tương thích."`. |
| 13 | Model Selector | Path traversal attack in model selector (e.g. `../../secret.pt`) | Path sanitization ensures requested file strictly resides within resolved `models/` folder. Returns HTTP 403 Forbidden on traversal attempt. |
| 14 | Model Selector | Hot-swapping model while a video stream is actively processing | Thread lock prevents race conditions: active frame completes with previous model, next frame uses new model seamlessly. |
| 15 | Visualization | Frame with 0 detected objects | Statistics return `current_objects_count = 0`, `current_avg_confidence = 0.0`. UI displays empty state without divide-by-zero errors. |
| 16 | Visualization | Very high number of detections (> 50 objects in frame) | UI renders top detections and limits table scroll height to prevent layout breakage. |
| 17 | Visualization | Non-standard video resolution (e.g. 4K, vertical 9:16 video) | Image is letterboxed / resized to 640x640 for inference, bounding boxes are accurately unpadded and scaled back to original resolution. |

---

## 8. Detailed Input/Output Specifications

### 8.1 REST API Endpoints

#### 1. `GET /`
- **Description**: Serves the main single-page application (HTML/CSS/JS) localized in Vietnamese.
- **Response**: `200 OK`, `Content-Type: text/html; charset=utf-8`.

#### 2. `GET /api/models`
- **Description**: Lists all detection models currently available in the `models/` directory.
- **Response**: `200 OK`, `Content-Type: application/json`
  ```json
  {
    "active_model": "yolo26n.pt",
    "models": [
      {
        "name": "yolo26n.pt",
        "size_mb": 5.29,
        "format": "pytorch",
        "is_active": true,
        "num_classes": 80
      }
    ]
  }
  ```

#### 3. `POST /api/models/select`
- **Description**: Hot-swaps the active detection model.
- **Request Body**: `application/json`
  ```json
  {
    "model_name": "yolo26n.pt"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "status": "success",
    "message": "Đã chuyển sang mô hình yolo26n.pt",
    "active_model": "yolo26n.pt",
    "classes": ["person", "bicycle", "car", "drone", "..."]
  }
  ```
- **Errors**: `400 Bad Request` (corrupted model), `404 Not Found` (model file not found).

#### 4. `POST /api/video/upload`
- **Description**: Uploads a video file (.mp4, .avi, .mkv) for processing.
- **Request**: `multipart/form-data` with `file: UploadFile`.
- **Response**: `200 OK`
  ```json
  {
    "video_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "filename": "sample_flight.mp4",
    "total_frames": 450,
    "fps": 30.0,
    "duration_sec": 15.0,
    "resolution": [1920, 1080],
    "status": "uploaded"
  }
  ```
- **Errors**: `400 Bad Request` (invalid extension, 0 bytes), `422 Unprocessable Entity` (corrupted headers).

#### 5. `GET /api/video/stream/{video_id}`
- **Description**: Streams processed frames in real-time.
- **Query Parameters**:
  - `conf`: float (default: `0.25`)
  - `iou`: float (default: `0.45`)
- **Response**: `200 OK`, `Content-Type: multipart/x-mixed-replace; boundary=frame`
  ```http
  --frame
  Content-Type: image/jpeg
  Content-Length: 45210

  <binary JPEG data>
  --frame
  ```

#### 6. `GET /api/video/stats/{video_id}`
- **Description**: Polling or SSE endpoint for live stats of video being processed.
- **Response**: `200 OK`, `Content-Type: application/json`
  ```json
  {
    "video_id": "a1b2c3d4-...",
    "status": "processing",
    "current_frame": 125,
    "total_frames": 450,
    "progress_percent": 27.8,
    "fps": 6.2,
    "latency_ms": 161.3,
    "current_objects_count": 2,
    "cumulative_objects_count": 18,
    "current_avg_confidence": 0.88,
    "overall_avg_confidence": 0.84,
    "elapsed_time_sec": 20.1,
    "detections": [
      {
        "class_id": 0,
        "class_name": "drone",
        "confidence": 0.91,
        "box": [450, 220, 620, 390]
      }
    ]
  }
  ```

#### 7. `GET /api/video/download/{video_id}`
- **Description**: Downloads the fully processed, annotated `.mp4` video.
- **Response**: `200 OK`, `Content-Type: video/mp4`, `Content-Disposition: attachment; filename="annotated_sample_flight.mp4"`.
- **Errors**: `404 Not Found` (if video not found or processing still incomplete).

---

### 8.2 WebSocket Protocol (`ws://localhost:PORT/ws/webcam`)

- **Protocol Lifecycle**:
  1. **Connection**: Client establishes `ws://localhost:PORT/ws/webcam`.
  2. **Config message (Client -> Server)**:
     ```json
     {
       "type": "config",
       "conf": 0.25,
       "iou": 0.45
     }
     ```
  3. **Frame message (Client -> Server)**:
     ```json
     {
       "type": "frame",
       "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
       "timestamp": 1727500000.123
     }
     ```
  4. **Detection message (Server -> Client)**:
     ```json
     {
       "type": "result",
       "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
       "fps": 6.4,
       "latency_ms": 156.2,
       "objects_count": 1,
       "avg_confidence": 0.89,
       "detections": [
         {
           "class_id": 0,
           "class_name": "drone",
           "confidence": 0.89,
           "box": [150, 100, 320, 280]
         }
       ]
     }
     ```

---

## 9. Comprehensive Vietnamese UI Localization Dictionary

| Key / Context | Vietnamese Term / Sentence | English Equivalent |
|---|---|---|
| **App Title** | Hệ Thống Phát Hiện & Theo Dõi Drone (Anti-Drone) | Drone Detection & Tracking System |
| **Subtitle** | Báo Cáo Đồ Án Tốt Nghiệp — Nhận Diện Đối Tượng Thời Gian Thực | Thesis Defense — Real-Time Object Detection Demo |
| **Mode Tab 1** | Tải lên Video | Upload Video |
| **Mode Tab 2** | Webcam Trực Tiếp | Live Webcam |
| **Model Label** | Mô hình phát hiện: | Detection Model: |
| **Model Swapping** | Đang nạp mô hình... | Loading model... |
| **Model Swap Success** | Đã kích hoạt mô hình: {name} | Activated model: {name} |
| **Model Swap Error** | Lỗi nạp mô hình: {detail} | Model loading error: {detail} |
| **Confidence Slider** | Ngưỡng tin cậy (Confidence): | Confidence Threshold: |
| **IoU Slider** | Ngưỡng trùng khớp (IoU): | IoU Threshold: |
| **Upload Prompt** | Kéo thả video vào đây hoặc nhấn để chọn tệp | Drag & drop video here or click to select |
| **Upload Supported** | Hỗ trợ định dạng: .mp4, .avi, .mkv (tối đa 500MB) | Supported formats: .mp4, .avi, .mkv (max 500MB) |
| **Btn Start** | Bắt đầu nhận diện | Start Detection |
| **Btn Pause** | Tạm dừng | Pause |
| **Btn Resume** | Tiếp tục | Resume |
| **Btn Stop** | Dừng lại | Stop |
| **Btn Download** | Tải xuống video đã nhận diện (.mp4) | Download Annotated Video (.mp4) |
| **Btn Camera On** | Bật Webcam | Turn on Webcam |
| **Btn Camera Off** | Tắt Webcam | Turn off Webcam |
| **Status Ready** | Trạng thái: Sẵn sàng | Status: Ready |
| **Status Processing** | Trạng thái: Đang xử lý ({progress}%) | Status: Processing ({progress}%) |
| **Status Completed** | Trạng thái: Hoàn thành | Status: Completed |
| **Stats Header** | Bảng Thống Kê Thời Gian Thực | Real-Time Statistics Panel |
| **Stat FPS** | Tốc độ xử lý (FPS) | Processing Speed (FPS) |
| **Stat Objects** | Số đối tượng phát hiện | Detected Objects Count |
| **Stat Avg Conf** | Độ tin cậy trung bình | Average Confidence |
| **Stat Latency** | Thời gian xử lý | Processing Latency |
| **Stat Total Time** | Tổng thời gian thực thi | Total Execution Time |
| **Table Time** | Thời điểm | Timestamp |
| **Table Class** | Lớp đối tượng | Class |
| **Table Confidence** | Độ tin cậy | Confidence |
| **Table Coordinates** | Tọa độ [x1, y1, x2, y2] | Coordinates [x1, y1, x2, y2] |
| **Err No Camera** | Không tìm thấy thiết bị camera trên máy tính. | No camera device found on computer. |
| **Err Cam Denied** | Quyền truy cập camera bị từ chối. Vui lòng cấp quyền trong trình duyệt. | Camera access denied. Please grant permission in browser. |
| **Err Invalid Format**| Định dạng tệp không được hỗ trợ (.mp4, .avi, .mkv). | Unsupported file format (.mp4, .avi, .mkv). |
| **Err Corrupted File**| Tệp video bị lỗi hoặc không thể đọc được. | Video file is corrupted or unreadable. |

---

## 10. Automated Verification Script Specification (`test_app.py`)

The verification script `test_app.py` in `web/` must execute autonomously with zero manual input, asserting the following steps and exiting with code `0`:
1. **Server Initialization**: Launches FastAPI instance via Uvicorn in background thread or via Starlette/FastAPI TestClient.
2. **Vietnamese HTML UI Check**: `GET /` returns `200 OK` with UTF-8 encoding and verifies key Vietnamese phrases ("Hệ Thống", "Tải lên Video", "Webcam Trực Tiếp", "Mô hình").
3. **Model Listing Check**: `GET /api/models` returns `200 OK` and includes `"yolo26n.pt"` with `is_active: true`.
4. **Model Selection Check**: `POST /api/models/select` with `{"model_name": "yolo26n.pt"}` returns `200 OK`.
5. **Simulated Webcam Frame Detection**:
   - Generates a synthetic 640x480 test image in-memory.
   - Sends image to frame detection endpoint.
   - Verifies response has `fps > 0`, `latency_ms > 0`, and `detections` list.
6. **Simulated Video Upload & Processing**:
   - Generates a synthetic 10-frame `.mp4` video in-memory using `cv2.VideoWriter`.
   - Sends multipart upload to `POST /api/video/upload`.
   - Verifies response contains valid `video_id` and `total_frames == 10`.
7. **Simulated Video Export**:
   - Requests download from `GET /api/video/download/{video_id}`.
   - Asserts response is `200 OK` and file length > 0.
8. **Edge Case Validation**:
   - Uploads 0-byte file -> asserts HTTP `400`.
   - Uploads corrupted file -> asserts HTTP `400` or `422`.
   - Requests nonexistent model -> asserts HTTP `404`.
9. **Exit Code**: Clean shutdown and `sys.exit(0)`.
