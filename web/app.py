import os
import cv2
import json
import base64
import uuid
import time
import asyncio
import threading
import numpy as np
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Ensure dirs exist
WEB_DIR = Path(__file__).parent
TMP_DIR = WEB_DIR / "tmp"
TMP_DIR.mkdir(exist_ok=True, parents=True)
STATIC_DIR = WEB_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "css").mkdir(exist_ok=True)
(STATIC_DIR / "js").mkdir(exist_ok=True)
TEMPLATES_DIR = WEB_DIR / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)

# Load backend
try:
    from backend.model_manager import ModelManager
    manager = ModelManager()
    print(f"[OK] ModelManager loaded")
except Exception as e:
    print(f"[WARN] ModelManager failed: {e}, using stub")
    manager = None

app = FastAPI(title="Hệ Thống Phát Hiện Drone")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from jinja2 import Environment, FileSystemLoader
_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), auto_reload=True)

# Video processing tasks
video_tasks = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    template = _jinja_env.get_template("index.html")
    return HTMLResponse(content=template.render())


@app.get("/api/models")
async def get_models():
    if manager is None:
        return {"models": [], "active": None}
    models_info = manager.list_models()
    result = []
    active_model = None
    for m in models_info:
        if isinstance(m, dict):
            info = m.copy()
            # Ensure 'display_name' exists for frontend
            if 'display_name' not in info:
                info['display_name'] = info.get('label', info.get('name', ''))
            result.append(info)
            if info.get('is_active'):
                active_model = info.get('name')
        else:
            name = getattr(m, 'name', str(m))
            display = getattr(m, 'display_name', getattr(m, 'label', name))
            is_active = getattr(m, 'is_active', False)
            result.append({"name": name, "display_name": display, "is_active": is_active})
            if is_active:
                active_model = name
    return {"models": result, "active": active_model}


@app.post("/api/models/switch")
async def switch_model(model_name: str = Form(...)):
    if manager is None:
        return {"status": "error", "message": "No model manager"}
    try:
        manager.set_active_model(model_name)
        return {"status": "success", "model": model_name}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/detect")
async def detect_image(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        return JSONResponse({"error": "Không đọc được ảnh"}, status_code=400)
    result = manager.predict(frame)
    # Return annotated image as base64
    _, buf = cv2.imencode('.jpg', result.annotated_frame)
    b64 = base64.b64encode(buf).decode('utf-8')
    resp = result.to_dict()
    resp['image'] = f"data:image/jpeg;base64,{b64}"
    return resp


def process_video_task(task_id: str, input_path: str, output_path: str):
    """Process video in background thread."""
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        video_tasks[task_id]['status'] = 'error'
        video_tasks[task_id]['message'] = 'Không mở được video'
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    video_tasks[task_id].update({
        'status': 'processing',
        'total_frames': total_frames,
        'processed_frames': 0,
        'fps_video': fps,
    })

    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        t0 = time.time()
        result = manager.predict(frame)
        dt = (time.time() - t0) * 1000

        annotated = result.annotated_frame
        if annotated is not None and annotated.size > 0:
            out.write(annotated)
            _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            video_tasks[task_id]['frame'] = buffer.tobytes()

        frame_idx += 1
        video_tasks[task_id].update({
            'processed_frames': frame_idx,
            'stats': {
                'total_detections': result.total_detections,
                'avg_confidence': round(result.avg_confidence, 4),
                'inference_time_ms': round(dt, 1),
                'fps': round(1000 / dt, 1) if dt > 0 else 0,
                'progress': round(frame_idx / max(total_frames, 1) * 100, 1),
            }
        })

    cap.release()
    out.release()
    video_tasks[task_id]['status'] = 'completed'


@app.post("/api/video/upload")
async def upload_video(file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())[:8]
    input_path = str(TMP_DIR / f"{task_id}_in.mp4")
    output_path = str(TMP_DIR / f"{task_id}_out.mp4")

    content = await file.read()
    with open(input_path, "wb") as f:
        f.write(content)

    video_tasks[task_id] = {'status': 'queued', 'frame': None, 'stats': {}}

    # Run in background thread
    t = threading.Thread(target=process_video_task, args=(task_id, input_path, output_path), daemon=True)
    t.start()

    return {"task_id": task_id, "filename": file.filename}


@app.get("/api/video/stream/{task_id}")
async def video_stream(task_id: str):
    """MJPEG stream of processed video frames."""
    async def generate():
        while True:
            if task_id not in video_tasks:
                break

            task = video_tasks[task_id]
            frame_bytes = task.get('frame')

            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                task['frame'] = None  # Consume frame

            if task['status'] == 'completed':
                # Send last frame one more time
                if frame_bytes:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                break

            await asyncio.sleep(0.03)  # ~30fps max

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/video/stats/{task_id}")
async def video_stats(task_id: str):
    if task_id in video_tasks:
        task = video_tasks[task_id]
        return {
            "status": task.get('status', 'unknown'),
            **task.get('stats', {}),
            "processed_frames": task.get('processed_frames', 0),
            "total_frames": task.get('total_frames', 0),
        }
    return {"status": "not_found"}


@app.get("/api/video/download/{task_id}")
async def download_video(task_id: str):
    output_path = TMP_DIR / f"{task_id}_out.mp4"
    if output_path.exists():
        return FileResponse(
            path=str(output_path),
            filename=f"drone_detect_{task_id}.mp4",
            media_type='video/mp4'
        )
    return JSONResponse({"error": "File chưa sẵn sàng"}, status_code=404)


@app.websocket("/ws/webcam")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if not data.startswith("data:image"):
                continue

            # Decode base64 image
            _, encoded = data.split(",", 1)
            img_data = base64.b64decode(encoded)
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                continue

            t0 = time.time()
            result = manager.predict(frame)
            dt = (time.time() - t0) * 1000

            _, buffer = cv2.imencode('.jpg', result.annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            b64_img = base64.b64encode(buffer).decode('utf-8')

            response = {
                "image": f"data:image/jpeg;base64,{b64_img}",
                "stats": {
                    "total_detections": result.total_detections,
                    "avg_confidence": round(result.avg_confidence, 4),
                    "inference_time_ms": round(dt, 1),
                    "fps": round(1000 / dt, 1) if dt > 0 else 0,
                }
            }
            await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS Error] {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("  HỆ THỐNG PHÁT HIỆN DRONE")
    print("  http://localhost:8000")
    print("=" * 50)
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
