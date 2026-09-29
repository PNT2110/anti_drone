# Original User Request

## 2026-09-28T03:14:54Z

Build a polished web-based object detection demo application for a university project presentation. The app runs locally on Windows, uses YOLO models via ultralytics, and supports both uploaded video files and live laptop webcam as input. The UI must be entirely in Vietnamese and look professional enough for a thesis defense demo. The architecture must support swapping in a custom-trained drone detection model later.

Working directory: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\web`
Integrity mode: development

The initial model is at: `c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\yolo26n.pt` (YOLO26n pretrained COCO, 5.3MB, 80 classes). A custom single-class drone model will replace this later.

Python 3.12 is installed at `C:\Users\pnt21\AppData\Local\Programs\Python\Python312\python.exe`. `ultralytics==8.4.121` is already installed globally.

## Requirements

### R1. Web Application with Dual Input Modes
A Python backend (Flask or FastAPI) serving an HTML/JS frontend that supports two detection modes:
- **Upload video**: User uploads a video file (.mp4, .avi, .mkv), the backend runs YOLO detection frame-by-frame, and streams the annotated result back to the browser in real-time.
- **Live webcam**: The browser captures the laptop's webcam feed and sends frames to the backend for detection, displaying annotated results in real-time with minimal latency.

### R2. Detection Visualization and Statistics
Each detection must be shown with:
- Bounding box overlay on the video/webcam frame
- Confidence score label next to each detection
- Live FPS counter displayed on the interface
- Summary statistics panel: total objects detected, average confidence, total processing time
- Ability to export the annotated video result as a downloadable file (for the video upload mode)

### R3. Professional Vietnamese UI
- All interface text, labels, buttons, and status messages in Vietnamese
- Clean, modern design suitable for a university thesis defense presentation
- Responsive layout that works on a laptop screen
- Clear visual distinction between the two modes (video upload vs webcam)

### R4. Model Backend Architecture (Extensible)
- Initially use `yolo26n.pt` via ultralytics Python API
- Design the detection backend so that additional model formats (ONNX, NCNN, other YOLO variants like yolov8n, yolo11n) can be added later as drop-in alternatives
- A model selector dropdown in the UI that lists available models from a `models/` directory
- When a custom drone model is added later, the app should work without code changes — just drop the `.pt` file in the models folder

## Acceptance Criteria

### Functional
- [ ] The web server starts successfully with `python app.py` (or equivalent single command) and is accessible at `http://localhost:PORT`
- [ ] Uploading a .mp4 video file produces a page showing the video with bounding boxes drawn around detected objects
- [ ] Webcam mode activates the laptop camera and displays live detection results in the browser at ≥5 FPS
- [ ] FPS counter is visible and updates in real-time during both modes
- [ ] Confidence scores are shown next to each bounding box
- [ ] Statistics panel shows detection count and processing time
- [ ] Annotated video can be downloaded after processing in video upload mode
- [ ] All visible text in the UI is in Vietnamese
- [ ] A model selector dropdown exists and lists at least the yolo26n.pt model
- [ ] Switching models via the dropdown changes the active detection model

### Technical
- [ ] The app runs on Windows with Python 3.12 without errors
- [ ] Required dependencies are listed in a `requirements.txt` and installable via `pip install -r requirements.txt`
- [ ] The app launches and loads the model in under 30 seconds on a modern laptop
- [ ] Adding a new `.pt` model file to the `models/` directory makes it appear in the dropdown without code changes

### Verification
- [ ] A test script `test_app.py` exists that: starts the server, uploads a sample video or synthetic test frame, verifies detection data in the response, and exits with code 0 on success
- [ ] Running `python test_app.py` passes without manual intervention


## 2026-09-28T03:50:42Z

IMPORTANT UPDATE: The trained drone detection models have been downloaded to the workspace. They are now available at:

**ONNX Models (drone single-class, ready for ultralytics/onnxruntime):**
- `models/yolov8n-drone-480.onnx` (11.6 MB)
- `models/yolov8n-drone-640.onnx` (11.7 MB)
- `models/yolo26n-drone-480.onnx` (9.3 MB)
- `models/yolo26n-drone-640.onnx` (9.3 MB)
- `models/yolo11n-drone-480.onnx` (10.0 MB)
- `models/yolo11n-drone-640.onnx` (10.1 MB)

**NCNN Models:**
- `models/ncnn-scope25-production/model.ncnn.{bin,param}` (production candidate)
- `models/ncnn-live-camera-v2/model.ncnn.{bin,param}`
- `models/ncnn-yolov8n/model.ncnn.{bin,param}`

**Also available:**
- `artifacts/deploy/yolov8n/tflite/model_float32.tflite` (11.6 MB)
- `yolo26n.pt` (5.3 MB, pretrained COCO - NOT drone-trained)

The ONNX models are the actual **drone-trained** models (single class: drone). They can be loaded with `ultralytics.YOLO('models/yolov8n-drone-640.onnx')`. The web app should use these as the primary models in the model selector dropdown, with labels like "YOLOv8n Drone 640", "YOLO26n Drone 480", etc.
