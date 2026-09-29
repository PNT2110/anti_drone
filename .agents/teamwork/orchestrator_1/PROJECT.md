# Project: Web-Based Anti-Drone Object Detection Demo Application

## Architecture
A high-performance, asynchronous web application running locally on Windows with Python 3.12, leveraging FastAPI, Uvicorn, Ultralytics YOLO, and OpenCV.
The application supports dual real-time input channels (Uploaded Video files and Live Laptop Webcam stream) with extensible YOLO detection backends (supporting both custom drone-trained ONNX models and baseline PyTorch `.pt` models), 100% Vietnamese localization, thesis-defense UI aesthetics, and automated end-to-end self-verification.

### Component Diagram & Data Flow
```
[ Browser Client (HTML5 / Modern JS / CSS) ]
       │
       ├── (1) Video Mode: HTTP POST (Multipart) -> Upload Video (.mp4, .avi, .mkv)
       │         │
       │         ▼
       │     FastAPI Video Service
       │         ├── Frame Decoder (OpenCV VideoCapture)
       │         ├── YOLO Detector Engine (Inference on CPU, Bounding Boxes, Labels)
       │         ├── Video Encoder (OpenCV VideoWriter 'mp4v' -> web/outputs/{id}.mp4)
       │         ├── MJPEG Stream Generator -> GET /api/video/stream/{id}
       │         └── Real-time Stats Polling / SSE -> GET /api/video/stats/{id}
       │
       ├── (2) Webcam Mode: WebSocket -> ws://localhost:PORT/ws/webcam
       │         │
       │         ├── Client: navigator.mediaDevices.getUserMedia -> Canvas -> JPEG Blob / Base64
       │         ├── Server: WebSocket Receiver -> Ping-Pong Flow Control (Drop queue)
       │         ├── Server: YOLO Detector Engine -> Bounding Boxes + Stats + Latency
       │         └── Client: Canvas Overlay rendering + Live FPS counter + Stats Dashboard
       │
       └── (3) Model Management: REST Endpoints
                 ├── GET /api/models -> Dynamic scan of models/ & root yolo26n.pt
                 └── POST /api/models/select -> Thread-safe hot swap via ModelManager
```

---

## Feature Inventory
Every feature from the Survey phase is mapped to an assigned milestone:

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Extensible Model Discovery | Dynamic discovery of all ONNX and PT models in `models/` and root | M1 | Survey / R4 |
| 2 | Thread-Safe Model Hot-Swapping | Runtime model swapping via UI without server restart | M1 | Survey / R4 |
| 3 | Core Detection Engine | YOLO inference runner, bounding box, confidence, label extraction | M1 | Survey / R1, R2 |
| 4 | Video File Upload | Accepts .mp4, .avi, .mkv via multipart upload, validates format | M2 | Survey / R1 |
| 5 | Real-Time Video Streaming | MJPEG frame-by-frame streaming with real-time detection overlay | M2 | Survey / R1 |
| 6 | Annotated Video Export | Encode annotated video with `mp4v` codec for download | M2 | Survey / R2 |
| 7 | Video Statistics & Progress | Per-video statistics (objects, avg conf, processing time, fps) | M2 | Survey / R2 |
| 8 | Live Webcam Capture & Streaming | WebRTC capture + WebSocket transmission with ping-pong flow control | M3 | Survey / R1 |
| 9 | Live Webcam Detection Protocol | Low-latency inference, real-time FPS calculation, overlay schema | M3 | Survey / R1, R2 |
| 10 | Real-Time FPS Counter | Live FPS counter visible and updating in real-time in both modes | M3, M4 | Survey / R2 |
| 11 | Summary Statistics Panel | Real-time dashboard showing total objects, avg confidence, total time | M1, M2, M3, M4 | Survey / R2 |
| 12 | 100% Vietnamese Localization | All UI labels, buttons, cards, toasts, and headers in Vietnamese | M4 | Survey / R3 |
| 13 | Thesis-Defense UI Styling | Clean, modern academic defense styling, deep navy/slate theme, responsive | M4 | Survey / R3 |
| 14 | Dual Mode Tabs & State Manager | Tab switcher between Video and Webcam with clean resource management | M4 | Survey / R1, R3 |
| 15 | Model Selector UI & Tuning | Dropdown model selector with friendly names and confidence/IoU sliders | M4 | Survey / R4 |
| 16 | E2E Test Suite & Test Runner | Standalone automated verification script `test_app.py` exiting 0 | M5 / E2E Track | Survey / Verification |

---

## Milestones
Target 5 milestones organized cleanly by architectural module boundaries:

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Backend Model Engine & Discovery | `web/backend/model_manager.py`, `detector.py`, `config.py` | None | PLANNED |
| M2 | Video Upload, Streaming & Export Service | `web/backend/video_service.py`, video endpoints in `app.py` | M1 | PLANNED |
| M3 | Live Webcam WebSocket Pipeline | `web/backend/webcam_service.py`, WebSocket endpoint in `app.py` | M1 | PLANNED |
| M4 | Vietnamese UI & Thesis-Defense Frontend | `web/static/index.html`, `style.css`, `app.js` | M1, M2, M3 | PLANNED |
| M5 | Final Verification & Hardening | `web/test_app.py`, `requirements.txt`, 100% E2E test pass | M1, M2, M3, M4, TEST_READY | PLANNED |

---

## Interface Contracts

### M1 (Model Engine) ↔ M2 (Video) & M3 (Webcam)
```python
class DetectionResult:
    boxes: list[list[float]]      # [[x1, y1, x2, y2], ...]
    confidences: list[float]      # [0.94, 0.88, ...]
    class_ids: list[int]          # [0, 0, ...]
    class_names: list[str]        # ["drone", "drone", ...]
    inference_time_ms: float      # e.g., 156.2
    annotated_frame: np.ndarray   # BGR image with drawn boxes/labels

class ModelManager:
    def list_models() -> list[dict]:
        """Returns list of available models with metadata: name, path, format, classes, is_active"""
    def set_active_model(model_name: str) -> bool:
        """Thread-safe model hot-swap. Returns True on success, raises on failure."""
    def predict(image: np.ndarray, conf: float = 0.25, iou: float = 0.45) -> DetectionResult:
        """Runs detection on a BGR image frame using the active model."""
```

### M2 (Video Service) ↔ Frontend (M4)
- `POST /api/video/upload` -> `{"video_id": str, "filename": str, "total_frames": int, "fps": float}`
- `GET /api/video/stream/{video_id}` -> `multipart/x-mixed-replace; boundary=frame`
- `GET /api/video/stats/{video_id}` -> `{"status": str, "progress": float, "fps": float, "total_detections": int, "avg_confidence": float, "elapsed_time_s": float}`
- `GET /api/video/download/{video_id}` -> Binary stream (`Content-Disposition: attachment; filename="{video_id}_detected.mp4"`)

### M3 (Webcam WebSocket) ↔ Frontend (M4)
- **Endpoint**: `ws://localhost:PORT/ws/webcam`
- **Client -> Server Frame**:
  `{"image": "data:image/jpeg;base64,...", "timestamp": 1727500000.123}` or raw binary JPEG.
- **Server -> Client Result**:
  ```json
  {
    "detections": [
      {"box": [120, 80, 240, 210], "label": "drone", "confidence": 0.94}
    ],
    "fps": 6.2,
    "inference_time_ms": 156.4,
    "total_objects": 1,
    "avg_confidence": 0.94,
    "annotated_image": "data:image/jpeg;base64,..."
  }
  ```

### M4 (Frontend) Vietnamese UI Terminology Dictionary
- Application Title: `HỆ THỐNG NHẬN DIỆN MÁY BAY KHÔNG NGƯỜI LÁI (ANTI-DRONE)`
- Tabs: `Tải lên Video` | `Webcam Trực tiếp`
- Controls: `Chọn Video`, `Bắt đầu Xử lý`, `Tạm dừng`, `Khởi động Camera`, `Dừng Camera`, `Tải về Video Kết quả`
- Model Selector: `Mô hình Nhận diện:` (e.g., "YOLOv8n Drone 480 (Khuyên dùng)", "YOLO26n Drone 480", "YOLOv8n Drone 640", "YOLO26n COCO (Mặc định)")
- Sliders: `Ngưỡng tin cậy (Confidence)` | `Ngưỡng giao nhau (IoU)`
- Dashboard Cards:
  - `Tốc độ khung hình (FPS)`
  - `Tổng số đối tượng phát hiện`
  - `Độ tin cậy trung bình`
  - `Thời gian xử lý`
  - `Trạng thái hệ thống: Sẵn sàng / Đang nhận diện / Đã hoàn thành`

---

## Code Layout
Strict separation of concerns under `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\web\`:

```
web/
├── app.py                     # Main FastAPI server entry point (single command: python app.py)
├── requirements.txt           # Python dependencies (fastapi, uvicorn, ultralytics, opencv-python, etc.)
├── test_app.py                # Standalone automated verification script (exits 0 on success)
├── backend/
│   ├── __init__.py
│   ├── config.py              # System paths, model definitions, default parameters
│   ├── model_manager.py       # Dynamic model discovery & thread-safe hot-swapping
│   ├── detector.py            # Ultralytics inference wrapper & visualization rendering
│   ├── video_service.py       # Video file decoding, MJPEG streaming & MP4 export
│   └── webcam_service.py      # Low-latency WebSocket handler & FPS tracking
├── static/
│   ├── css/
│   │   └── style.css          # Thesis-defense modern styling (deep navy/slate theme)
│   ├── js/
│   │   ├── app.js             # UI state controller, tab switcher, model dropdown
│   │   ├── video_player.js    # Video upload & MJPEG playback controller
│   │   └── webcam_streamer.js # WebRTC camera capture & WebSocket client
│   └── index.html             # Single-page application in 100% Vietnamese
├── models/                    # Dropped-in drone and YOLO models
│   ├── yolov8n-drone-480.onnx
│   ├── yolov8n-drone-640.onnx
│   ├── yolo26n-drone-480.onnx
│   ├── yolo26n-drone-640.onnx
│   ├── yolo11n-drone-480.onnx
│   ├── yolo11n-drone-640.onnx
│   └── yolo26n.pt
└── outputs/                   # Annotated export videos storage
```

---

## Dual Track Strategy
1. **Implementation Track**:
   - Executes milestones M1 -> M2 -> M3 -> M4 -> M5 sequentially/iteratively.
   - Each milestone uses the complete Explorer -> Worker -> Reviewer -> Challenger -> Auditor -> Gate cycle.
   - Final milestone (M5) verifies 100% pass of E2E test suite + Tier 5 coverage hardening.
2. **E2E Testing Track**:
   - Runs in parallel to design and construct the opaque-box test suite (`TEST_INFRA.md`).
   - Generates Tiers 1-4 test cases (Feature Coverage, Boundary/Corner, Cross-Feature, Real-World Application).
   - Generates standalone `test_app.py` automated verification test.
   - Publishes `TEST_READY.md` upon completion.
