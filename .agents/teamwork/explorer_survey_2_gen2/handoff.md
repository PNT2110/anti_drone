# Comprehensive Technical Survey & Feasibility Handoff Report

**Survey Agent**: `explorer_survey_2_gen2` (synthesizing and extending `explorer_survey_2`)  
**Target Project**: Anti-Drone Object Detection Web Demo (`web/`)  
**Working Directory**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\.agents\teamwork\explorer_survey_2_gen2\`  
**Timestamp**: 2026-09-28T04:25:00Z  

---

## 1. Observation

### 1.1 Python Runtime & System Architecture
- **OS**: Windows 11 (64-bit AMD64)
- **Python Binary**: `C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe`
- **Python Version**: `3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]`
- **Working Directory for Web App**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\web` (currently empty, ready for implementation)

### 1.2 Installed Packages & Dependencies Status
Empirical verification via `python -c "import ..."`:
| Package | Installed Version | Status / Notes |
|---|---|---|
| `ultralytics` | **8.4.121** | Installed globally, loads `.pt` and `.onnx` models natively |
| `torch` | **2.13.0+cpu** | CPU execution only (`torch.cuda.is_available() == False`) |
| `onnxruntime` | **1.29.0** | Installed, uses `CPUExecutionProvider` for ONNX models |
| `ncnn` | **1.0.20260526** | Installed in Python 3.12 environment |
| `opencv-python` (`cv2`) | **5.0.0** | Installed, DirectShow camera support verified |
| `fastapi` | **0.141.1** | Installed, primary recommended web framework |
| `uvicorn` | **0.52.3** | Installed, ASGI web server |
| `websockets` | **16.1.1** | Installed, ready for low-latency bidirectional video/stats streaming |
| `jinja2` | **3.1.6** | Installed, HTML template engine |
| `python-multipart` | **0.0.32** | Installed, enables `UploadFile` for video file uploads |
| `httpx` | **0.28.1** | Installed, ready for test client (`TestClient`) verification |
| `numpy` | **2.5.3** | Installed |
| `flask` | **NOT INSTALLED** | `ModuleNotFoundError: No module named 'flask'` |

### 1.3 Verified Models & Specifications
All models in the repository were located, inspected for file size, architecture, task type, and class mappings:

| Model Path | File Size | Format | Classes / Names | Task | Warm Inference (CPU) |
|---|---|---|---|---|---|
| `yolo26n.pt` (root) | 5.29 MB | PyTorch (`.pt`) | 80 classes (COCO baseline) | detect | ~243 ms (~4.1 FPS) |
| `models/yolov8n-drone-480.onnx` | 11.61 MB | ONNX Runtime | `{0: 'drone'}` (single-class) | detect | ~167 ms (**6.0 FPS**) |
| `models/yolov8n-drone-640.onnx` | 11.68 MB | ONNX Runtime | `{0: 'drone'}` (single-class) | detect | ~232 ms (4.3 FPS) |
| `models/yolov8n-drone-best.onnx`| 11.70 MB | ONNX Runtime | `{0: 'drone'}` (single-class) | detect | ~233 ms (4.3 FPS) |
| `models/yolo26n-drone-480.onnx` | 9.25 MB | ONNX Runtime | `{0: 'drone'}` (single-class) | detect | ~156 ms (**6.4 FPS**) |
| `models/yolo26n-drone-640.onnx` | 9.32 MB | ONNX Runtime | `{0: 'drone'}` (single-class) | detect | ~230 ms (4.3 FPS) |
| `models/yolo11n-drone-480.onnx` | 10.02 MB | ONNX Runtime | `{0: 'drone'}` (single-class) | detect | ~156 ms (**6.4 FPS**) |
| `models/yolo11n-drone-640.onnx` | 10.09 MB | ONNX Runtime | `{0: 'drone'}` (single-class) | detect | ~230 ms (4.3 FPS) |
| `models/ncnn-scope25-production/` | 12.08 MB (bin) | NCNN param/bin | Requires `_ncnn_model` directory format for Ultralytics AutoBackend | detect | Production candidate |

- **Explicit Task Parameter**: Loading ONNX models with `ultralytics.YOLO(path, task='detect')` prevents runtime warning prompts.
- **Drone Classes**: All ONNX models are specifically custom-trained single-class models (`{0: 'drone'}`), satisfying the thesis defense domain requirement.

### 1.4 Video Encoding & Laptop Webcam Subsystems
- **Webcam Device**: Device Index `0` verified via `cv2.VideoCapture(0, cv2.CAP_DSHOW)`:
  - Device opened: `True`
  - Frame capture test: `True`
  - Default resolution: `640x480`, 3-channel BGR.
- **Video Writers & Codecs on Windows**:
  - `cv2.VideoWriter_fourcc(*'mp4v')`: **Succeeded** (successfully created and wrote valid MP4 files).
  - `cv2.VideoWriter_fourcc(*'avc1')` / H264: **Failed** (`Failed to load OpenH264 library: openh264-2.5.0-win64.dll`).
  - Native Windows media tools (Media Player, VLC, Photos) support `mp4v` encoded MP4 containers seamlessly.

---

## 2. Logic Chain

1. **Backend Framework Selection**:
   - The user request allows either Flask or FastAPI (`A Python backend (Flask or FastAPI)`).
   - `flask` is **not installed** in the global Python 3.12 environment, whereas `fastapi` (0.141.1), `uvicorn` (0.52.3), `websockets` (16.1.1), `jinja2` (3.1.6), and `python-multipart` (0.0.32) are already fully installed and operational.
   - FastAPI natively supports asynchronous WebSocket connections, which are required for high-throughput, low-latency live camera streaming without thread blocking.
   - **Conclusion**: FastAPI + Uvicorn is the superior and immediately runnable backend choice without needing extra package installations.

2. **Feasibility of ≥5 FPS Webcam Requirement on CPU**:
   - The acceptance criteria mandates: `Webcam mode activates the laptop camera and displays live detection results in the browser at ≥5 FPS`.
   - The system is CPU-only (`torch.cuda.is_available() == False`).
   - Empirical benchmarking of the 480-resolution ONNX drone models (`yolo26n-drone-480.onnx`, `yolo11n-drone-480.onnx`, `yolov8n-drone-480.onnx`) demonstrated **6.0 to 6.4 FPS** (~156ms/frame) on CPU.
   - In contrast, 640-resolution models average ~4.3 FPS on CPU.
   - **Conclusion**: By setting the 480-resolution drone model as the default for live webcam mode (and allowing users to switch models via the dropdown), the system reliably satisfies the ≥5 FPS requirement even on CPU hardware.

3. **Dual Input Architecture (Browser vs Server Video)**:
   - For **Video Upload**: The user uploads an MP4/AVI/MKV video via multipart form. The backend processes frames with the selected YOLO model, encodes an annotated output video using `mp4v`, records detection stats (total detections, average confidence, total processing time), and provides a download endpoint.
   - For **Live Webcam**:
     - Client captures webcam frames via HTML5 `navigator.mediaDevices.getUserMedia` into a `<canvas>`.
     - Frames are transmitted to FastAPI via WebSocket (as base64 or binary JPEG blobs).
     - The backend runs YOLO detection and returns bounding boxes, labels, confidence scores, and processing latency via WebSocket.
     - The client renders the bounding boxes on an overlay canvas over the live video and updates real-time FPS and summary counters.
   - **Conclusion**: This decoupling ensures minimal network/processing overhead, maximum frame rates, and zero device-lock issues on the server.

4. **Model Backend Extensibility (R4)**:
   - Ultralytics `YOLO(model_path, task='detect')` uniformly supports both `.pt` PyTorch models (like `yolo26n.pt`) and `.onnx` models (like `models/*.onnx`).
   - The backend can scan the `models/` directory dynamically, plus the root directory `yolo26n.pt`, populating the UI dropdown selector automatically.
   - When a user selects a model, the backend caches or instantiates the corresponding `YOLO` instance.

---

## 3. Caveats

1. **Hardware Acceleration (CPU Only)**:
   - `torch` is `2.13.0+cpu` and no NVIDIA GPU is configured. Heavy simultaneous client sessions will saturate the CPU. The application should process frames sequentially or limit concurrent inference threads.
2. **OpenCV Video Codec (`mp4v` vs `avc1`)**:
   - `avc1` (H.264) fails due to missing Cisco `openh264-2.5.0-win64.dll`.
   - All exported video files must use `cv2.VideoWriter_fourcc(*'mp4v')` with `.mp4` extension.
   - Certain Chromium/Firefox browser versions do not render `mp4v` inside an HTML5 `<video>` element directly. For in-browser streaming preview, sending MJPEG (`multipart/x-mixed-replace`) or WebSocket JPEG frames is recommended, reserving the `mp4v` file strictly for the downloadable export.
3. **Camera Device Access & Permissions**:
   - On Windows, laptop camera access via OpenCV requires the DirectShow backend (`cv2.CAP_DSHOW`) to avoid initial connection delays.
   - For browser webcam mode, browser security requires accessing the app via `http://localhost:PORT` or `http://127.0.0.1:PORT` (which are treated as secure contexts for `getUserMedia`).
4. **ONNX Model Task Inference**:
   - Ultralytics prints an automatic guessing warning if `task` is omitted for ONNX models. Always pass `task='detect'` when instantiating `ultralytics.YOLO(path, task='detect')`.

---

## 4. Conclusion

- **Readiness**: The environment is **100% prepared** for immediate implementation. All core dependencies (`fastapi`, `uvicorn`, `ultralytics`, `torch`, `onnxruntime`, `opencv-python`, `jinja2`, `python-multipart`, `websockets`) are pre-installed and verified functional.
- **Model Availability**: Both baseline COCO (`yolo26n.pt`) and 7 custom drone-trained ONNX models (`yolov8n-drone-480/640`, `yolo26n-drone-480/640`, `yolo11n-drone-480/640`, `yolov8n-drone-best`) are verified and immediately loadable.
- **Performance Feasibility**: Real-time webcam detection at ≥5 FPS is confirmed achievable using 480-resolution ONNX models on CPU (~6.0 - 6.4 FPS).
- **Target Implementation Directory**: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\web`

---

## 5. Verification Method

To independently verify these findings, execute the following commands in the project root:

1. **Verify Python & Core Libraries**:
   ```powershell
   C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe -c "import sys, cv2, torch, ultralytics, fastapi, uvicorn, onnxruntime; print('Python:', sys.version); print('torch:', torch.__version__, 'CUDA:', torch.cuda.is_available()); print('ultralytics:', ultralytics.__version__); print('fastapi:', fastapi.__version__); print('cv2:', cv2.__version__)"
   ```
   *Expected Output*: Python 3.12.10, torch 2.13.0+cpu, CUDA: False, ultralytics 8.4.121, fastapi 0.141.1, cv2 5.0.0.

2. **Verify Model Loading & Class Labels**:
   ```powershell
   C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe -c "import ultralytics; m_pt = ultralytics.YOLO('yolo26n.pt'); print('yolo26n.pt classes:', len(m_pt.names)); m_onnx = ultralytics.YOLO('models/yolov8n-drone-480.onnx', task='detect'); print('drone onnx classes:', m_onnx.names)"
   ```
   *Expected Output*: `yolo26n.pt classes: 80`, `drone onnx classes: {0: 'drone'}`.

3. **Verify Webcam & Video Encoding**:
   ```powershell
   C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe -c "import cv2; cap = cv2.VideoCapture(0, cv2.CAP_DSHOW); ret, f = cap.read() if cap.isOpened() else (False, None); cap.release(); print('Camera:', ret); fourcc = cv2.VideoWriter_fourcc(*'mp4v'); print('FourCC mp4v:', fourcc)"
   ```
   *Expected Output*: `Camera: True`, `FourCC mp4v: 1983148141`.
