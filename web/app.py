import os
import sys
import cv2
import json
import atexit
import base64
import binascii
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
from backend.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    MAX_UPLOAD_SIZE_BYTES,
    SUPPORTED_VIDEO_EXTENSIONS,
)
from backend.tracker import IdentityTracker, create_tracker_from_env
from security import BasicAuthMiddleware, get_password, is_loopback

# Log lines contain Vietnamese. When output is redirected (start.bat writes to
# server.log) Windows falls back to a legacy code page and print() would raise.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

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
PID_FILE = WEB_DIR / "server.pid"

# Load backend
try:
    from backend.model_manager import ModelManager
    manager = ModelManager()
    print(f"[OK] ModelManager loaded")
except Exception as e:
    print(f"[WARN] ModelManager failed: {e}, using stub")
    manager = None

app = FastAPI(title="Hệ Thống Phát Hiện Drone")
app.add_middleware(BasicAuthMiddleware)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

from jinja2 import Environment, FileSystemLoader
_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), auto_reload=True)

# Video processing tasks.  Worker threads and request handlers both touch this
# registry, so every access goes through video_tasks_lock.
video_tasks = {}
video_tasks_lock = threading.Lock()
ACTIVE_TASK_STATES = ("queued", "processing")
UPLOAD_CHUNK_BYTES = 1024 * 1024
NO_MODEL_MESSAGE = "Chưa nạp được mô hình. Kiểm tra thư mục models/ và log server."


def no_model_response() -> JSONResponse:
    return JSONResponse({"status": "error", "error": NO_MODEL_MESSAGE, "message": NO_MODEL_MESSAGE}, status_code=503)


def reset_tracking() -> None:
    """Reset only stream identity state; keep the loaded model warm."""

    if manager is not None and hasattr(manager, "_active_detector"):
        detector = manager._active_detector
        if detector is not None and hasattr(detector, "reset_tracking"):
            detector.reset_tracking()


def create_stream_tracker() -> IdentityTracker:
    """Create isolated ID memory for one uploaded video or camera connection."""

    return create_tracker_from_env()


def tracked_stats(result) -> tuple[int, float, list[int]]:
    """Count, mean confidence and IDs of the boxes the tracker has confirmed.

    Raw detector output also contains low-confidence and one-frame boxes that
    are never drawn, so the UI numbers are taken from tracked objects only.
    """

    confidences = [
        confidence
        for confidence, track_id in zip(result.confidences, result.track_ids)
        if track_id is not None
    ]
    track_ids = [int(track_id) for track_id in result.track_ids if track_id is not None]
    average = float(np.mean(confidences)) if confidences else 0.0
    return len(confidences), round(average, 4), track_ids


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    ok, buffer = cv2.imencode(
        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, int(max(40, min(95, quality)))]
    )
    if not ok:
        return b""
    return buffer.tobytes()


@app.middleware("http")
async def reject_oversize_upload(request: Request, call_next):
    # Refuse before the multipart body is received and spooled to disk.
    if request.url.path == "/api/video/upload":
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_UPLOAD_SIZE_BYTES + UPLOAD_CHUNK_BYTES:
            return JSONResponse({"error": "Video vượt quá dung lượng cho phép."}, status_code=413)
    return await call_next(request)


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
        return no_model_response()
    try:
        # Loading and warming a model can take seconds; keep the event loop free.
        await asyncio.to_thread(manager.set_active_model, model_name)
        return {"status": "success", "model": model_name}
    except KeyError:
        # ModelNotFoundError derives from KeyError.
        return JSONResponse(
            {"status": "error", "message": f"Không tìm thấy mô hình '{model_name}'."},
            status_code=404,
        )
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/detect")
async def detect_image(file: UploadFile = File(...)):
    if manager is None:
        return no_model_response()
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    # cv2.imdecode raises on an empty buffer instead of returning None.
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR) if nparr.size else None
    if frame is None:
        return JSONResponse({"error": "Không đọc được ảnh"}, status_code=400)
    # A still image is its own stream: IDs must not leak between requests.
    # There is no second frame to confirm a box on, so confirm immediately.
    result = await asyncio.to_thread(
        manager.predict, frame, tracker=create_tracker_from_env(confirm_hits=1)
    )
    # Return annotated image as base64
    _, buf = cv2.imencode('.jpg', result.annotated_frame)
    b64 = base64.b64encode(buf).decode('utf-8')
    resp = result.to_dict()
    resp['image'] = f"data:image/jpeg;base64,{b64}"
    return resp


def update_video_task(task_id: str, **fields) -> None:
    with video_tasks_lock:
        task = video_tasks.get(task_id)
        if task is not None:
            task.update(fields)


def prune_video_tasks(now: float | None = None) -> None:
    """Drop finished tasks and temp videos older than the retention window."""

    now = time.time() if now is None else now
    ttl = float(os.getenv("ANTI_DRONE_VIDEO_TTL_SECONDS", "3600"))
    with video_tasks_lock:
        expired = [
            task_id
            for task_id, task in video_tasks.items()
            if task.get('status') not in ACTIVE_TASK_STATES
            and now - task.get('finished_at', now) > ttl
        ]
        for task_id in expired:
            del video_tasks[task_id]
        live_ids = set(video_tasks)

    for pattern in ("*_in.*", "*_out.mp4"):
        for path in TMP_DIR.glob(pattern):
            if path.name.split("_", 1)[0] in live_ids:
                continue
            try:
                if now - path.stat().st_mtime > ttl:
                    path.unlink()
            except OSError:
                pass


def process_video_task(task_id: str, input_path: str, output_path: str):
    """Process and stream a video in source-time order, not all-at-once."""
    cap = None
    out = None
    seen_ids = set()
    try:
        if manager is None:
            raise RuntimeError(NO_MODEL_MESSAGE)
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise RuntimeError('Không mở được video')

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not out.isOpened():
            raise RuntimeError('Không tạo được video kết quả')

        stream_tracker = create_stream_tracker()
        frame_interval = 1.0 / max(float(fps), 1.0)
        next_frame_deadline = time.perf_counter()

        update_video_task(
            task_id,
            status='processing',
            total_frames=total_frames,
            processed_frames=0,
            fps_video=fps,
            frame_seq=0,
            unique_track_ids=[],
            detection_observations=0,
        )

        frame_idx = 0
        frame_seq = 0
        detection_observations = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            t0 = time.perf_counter()
            result = manager.predict(
                frame,
                  # Let weak detections participate in track continuation, but
                  # decide separately which unmatched boxes are safe to display.
                  draw=False,
                  # Keep weak detections available to continue a known small FPV
                  # track; the tracker requires >=0.25 confidence to create a new ID.
                  conf=float(os.getenv("ANTI_DRONE_VIDEO_MIN_CONFIDENCE", "0.10")),
                  # FPV drones occupy very few pixels in these source videos; 960
                  # improves small-object recall and gives the tracker more
                  # continuous observations while remaining real-time on the server.
                  imgsz=960,
                tracker=stream_tracker,
                timestamp=frame_idx / max(float(fps), 1.0),
            )
            dt = (time.perf_counter() - t0) * 1000.0

            # Draw only what the tracker has confirmed. A box without an ID is
            # either low-confidence clutter or has not persisted long enough.
            visible_indices = [
                index
                for index, track_id in enumerate(result.track_ids)
                if track_id is not None
            ]
            detector = getattr(manager, "_active_detector", None)
            if detector is not None and hasattr(detector, "draw_styled_detections"):
                annotated = detector.draw_styled_detections(
                    frame=frame,
                    boxes=[result.boxes[index] for index in visible_indices],
                    confidences=[result.confidences[index] for index in visible_indices],
                    class_ids=[result.class_ids[index] for index in visible_indices],
                    class_names=[result.class_names[index] for index in visible_indices],
                    track_ids=[result.track_ids[index] for index in visible_indices],
                )
            else:
                annotated = result.annotated_frame

            frame_idx += 1
            tracked_count, tracked_confidence, tracked_ids = tracked_stats(result)
            seen_ids.update(tracked_ids)
            detection_observations += tracked_count
            fields = {
                'processed_frames': frame_idx,
                'unique_track_ids': sorted(seen_ids),
                'detection_observations': detection_observations,
                'stats': {
                    'total_detections': tracked_count,
                    'avg_confidence': tracked_confidence,
                    'inference_time_ms': round(dt, 1),
                    # This is the paced output rate, not raw inference throughput.
                    # The UI must tell the truth about real-time playback.
                    'fps': round(float(fps), 1),
                    'progress': round(frame_idx / max(total_frames, 1) * 100, 1),
                    'track_ids': tracked_ids,
                },
            }
            if annotated is not None and annotated.size > 0:
                out.write(annotated)
                frame_seq += 1
                fields['frame'] = encode_jpeg(annotated, 82)
                fields['frame_seq'] = frame_seq
            update_video_task(task_id, **fields)

            # Pace playback to the source video.  This makes the web preview a
            # live processing view instead of a benchmark that jumps to the end.
            next_frame_deadline += frame_interval
            delay = next_frame_deadline - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            elif delay < -frame_interval * 3:
                next_frame_deadline = time.perf_counter()

        # Release the writer before announcing completion so the download is whole.
        out.release()
        out = None
        update_video_task(task_id, status='completed', finished_at=time.time())
    except Exception as e:
        print(f"[Video task {task_id} error] {e}")
        update_video_task(task_id, status='error', message=str(e), finished_at=time.time())
    finally:
        if cap is not None:
            cap.release()
        if out is not None:
            out.release()


@app.post("/api/video/upload")
async def upload_video(file: UploadFile = File(...)):
    if manager is None:
        return no_model_response()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_VIDEO_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_VIDEO_EXTENSIONS))
        return JSONResponse({"error": f"Định dạng không hỗ trợ. Chấp nhận: {allowed}"}, status_code=400)

    prune_video_tasks()
    task_id = uuid.uuid4().hex
    max_tasks = int(os.getenv("ANTI_DRONE_MAX_VIDEO_TASKS", "2"))
    with video_tasks_lock:
        active = sum(1 for task in video_tasks.values() if task.get('status') in ACTIVE_TASK_STATES)
        if active >= max_tasks:
            return JSONResponse(
                {"error": "Server đang xử lý tối đa số video cho phép. Thử lại sau."},
                status_code=429,
            )
        # Reserve the slot before the (slow) write so concurrent uploads cannot overshoot.
        video_tasks[task_id] = {'status': 'queued', 'frame': None, 'frame_seq': 0, 'stats': {}}

    input_path = TMP_DIR / f"{task_id}_in{suffix}"
    output_path = TMP_DIR / f"{task_id}_out.mp4"
    written = 0
    rejection = None
    try:
        with open(input_path, "wb") as f:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_SIZE_BYTES:
                    rejection = JSONResponse({"error": "Video vượt quá dung lượng cho phép."}, status_code=413)
                    break
                f.write(chunk)
        if rejection is None and written == 0:
            rejection = JSONResponse({"error": "Tệp video rỗng."}, status_code=400)
    except Exception:
        rejection = JSONResponse({"error": "Không lưu được video."}, status_code=500)

    if rejection is not None:
        with video_tasks_lock:
            video_tasks.pop(task_id, None)
        input_path.unlink(missing_ok=True)
        return rejection

    # Run in background thread
    t = threading.Thread(target=process_video_task, args=(task_id, str(input_path), str(output_path)), daemon=True)
    t.start()

    return {"task_id": task_id, "filename": file.filename}


@app.get("/api/video/stream/{task_id}")
async def video_stream(task_id: str):
    """MJPEG stream of processed video frames."""
    with video_tasks_lock:
        if task_id not in video_tasks:
            return JSONResponse({"status": "not_found"}, status_code=404)

    async def generate():
        last_frame_seq = -1
        while True:
            with video_tasks_lock:
                task = video_tasks.get(task_id)
                if task is None:
                    break
                frame_bytes = task.get('frame')
                frame_seq = task.get('frame_seq', 0)
                status = task.get('status')

            if frame_bytes and frame_seq != last_frame_seq:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                last_frame_seq = frame_seq

            if status in ('completed', 'error'):
                # Send last frame one more time
                if frame_bytes:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                break

            await asyncio.sleep(0.03)  # ~30fps max

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/video/stats/{task_id}")
async def video_stats(task_id: str):
    with video_tasks_lock:
        task = video_tasks.get(task_id)
        if task is None:
            return JSONResponse({"status": "not_found"}, status_code=404)
        stats = dict(task.get('stats', {}))
        return {
            "status": task.get('status', 'unknown'),
            **stats,
            "message": task.get('message'),
            "processed_frames": task.get('processed_frames', 0),
            "total_frames": task.get('total_frames', 0),
            "track_ids": stats.get('track_ids', []),
            "unique_track_ids": list(task.get('unique_track_ids', [])),
            "detection_observations": task.get('detection_observations', 0),
        }


@app.get("/api/video/download/{task_id}")
async def download_video(task_id: str):
    # Only serve outputs of known, finished tasks; never build a path from an
    # arbitrary client-supplied id.
    with video_tasks_lock:
        task = video_tasks.get(task_id)
        ready = task is not None and task.get('status') == 'completed'
    output_path = TMP_DIR / f"{task_id}_out.mp4"
    if ready and output_path.exists():
        return FileResponse(
            path=str(output_path),
            filename=f"drone_detect_{task_id}.mp4",
            media_type='video/mp4'
        )
    return JSONResponse({"error": "File chưa sẵn sàng"}, status_code=404)


async def reject_websocket_without_model(websocket: WebSocket) -> bool:
    if manager is not None:
        return False
    await websocket.send_text(json.dumps({"error": NO_MODEL_MESSAGE}))
    await websocket.close(code=1011)
    return True


@app.websocket("/ws/webcam")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    if await reject_websocket_without_model(websocket):
        return
    stream_tracker = create_stream_tracker()
    try:
        while True:
            data = await websocket.receive_text()
            if not data.startswith("data:image"):
                continue

            # Decode base64 image; one corrupt frame must not end the session.
            try:
                _, encoded = data.split(",", 1)
                img_data = base64.b64decode(encoded)
            except (ValueError, binascii.Error):
                continue
            nparr = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR) if nparr.size else None

            if frame is None:
                continue

            t0 = time.time()
            # Webcam prioritizes responsiveness: the detector receives a smaller
            # inference canvas while the browser still displays the full result.
            result = await asyncio.to_thread(
                manager.predict,
                frame,
                imgsz=480,
                tracker=stream_tracker,
            )
            dt = (time.time() - t0) * 1000

            _, buffer = cv2.imencode('.jpg', result.annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            b64_img = base64.b64encode(buffer).decode('utf-8')

            tracked_count, tracked_confidence, tracked_ids = tracked_stats(result)
            response = {
                "image": f"data:image/jpeg;base64,{b64_img}",
                "stats": {
                    "total_detections": tracked_count,
                    "avg_confidence": tracked_confidence,
                    "inference_time_ms": round(dt, 1),
                    "fps": round(1000 / dt, 1) if dt > 0 else 0,
                    "track_ids": tracked_ids,
                }
            }
            await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS Error] {e}")


@app.websocket("/ws/camera")
async def server_camera_endpoint(websocket: WebSocket):
    """Capture the USB camera attached to the inference server.

    The browser never asks for camera permission.  This is required when the
    web page is opened by IP over HTTP, where getUserMedia is blocked by the
    browser's secure-context policy.
    """

    await websocket.accept()
    if await reject_websocket_without_model(websocket):
        return
    camera_index = int(os.getenv("ANTI_DRONE_CAMERA_INDEX", "0"))
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        await websocket.send_text(json.dumps({
            "error": f"Không mở được camera server index={camera_index}. Kiểm tra USB hoặc ANTI_DRONE_CAMERA_INDEX."
        }))
        await websocket.close(code=1011)
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(os.getenv("ANTI_DRONE_CAMERA_WIDTH", "1280")))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(os.getenv("ANTI_DRONE_CAMERA_HEIGHT", "720")))
    stream_tracker = create_stream_tracker()
    target_fps = max(1.0, float(os.getenv("ANTI_DRONE_CAMERA_FPS", "15")))
    frame_interval = 1.0 / target_fps
    try:
        while True:
            started = time.perf_counter()
            ok, frame = await asyncio.to_thread(cap.read)
            if not ok:
                await websocket.send_text(json.dumps({"error": "Camera server không trả frame."}))
                break
            t0 = time.perf_counter()
            result = await asyncio.to_thread(
                manager.predict,
                frame,
                imgsz=640,
                tracker=stream_tracker,
            )
            inference_ms = (time.perf_counter() - t0) * 1000.0
            encoded = await asyncio.to_thread(encode_jpeg, result.annotated_frame, 82)
            b64_img = base64.b64encode(encoded).decode("ascii")
            tracked_count, tracked_confidence, tracked_ids = tracked_stats(result)
            await websocket.send_text(json.dumps({
                "image": f"data:image/jpeg;base64,{b64_img}",
                "stats": {
                    "total_detections": tracked_count,
                    "avg_confidence": tracked_confidence,
                    "inference_time_ms": round(inference_ms, 1),
                    "fps": round(1.0 / max(time.perf_counter() - started, 1e-6), 1),
                    "track_ids": tracked_ids,
                },
            }))
            delay = frame_interval - (time.perf_counter() - started)
            if delay > 0:
                await asyncio.sleep(delay)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[Server camera error] {e}")
    finally:
        cap.release()


if __name__ == "__main__":
    if not is_loopback(DEFAULT_HOST) and get_password() is None:
        raise SystemExit(
            f"Từ chối chạy trên {DEFAULT_HOST} khi chưa đặt mật khẩu. "
            "Đặt ANTI_DRONE_PASSWORD, hoặc dùng ANTI_DRONE_HOST=127.0.0.1."
        )
    # stop.bat reads this to stop only this server, not every python.exe.
    PID_FILE.write_text(str(os.getpid()), encoding="ascii")
    atexit.register(lambda: PID_FILE.unlink(missing_ok=True))
    print("=" * 50)
    print("  HỆ THỐNG PHÁT HIỆN DRONE")
    print(f"  http://{DEFAULT_HOST}:{DEFAULT_PORT}")
    print(f"  Mật khẩu: {'đã bật' if get_password() else 'TẮT (chỉ truy cập nội bộ)'}")
    print("=" * 50)
    # Pass the object: "app:app" would import this module a second time and
    # load the model twice.
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)
