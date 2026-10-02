"""HTTP/WebSocket contract tests against the real FastAPI app."""

from __future__ import annotations

import base64
import os
import time

import cv2
import numpy as np
import pytest
from starlette.websockets import WebSocketDisconnect


def make_video_bytes(tmp_path, frames: int = 5) -> bytes:
    path = tmp_path / "source_fixture.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (64, 64))
    assert writer.isOpened()
    for index in range(frames):
        frame = np.full((64, 64, 3), (40 + index * 5) % 256, dtype=np.uint8)
        cv2.rectangle(frame, (10, 10), (40, 40), (0, 0, 255), -1)
        writer.write(frame)
    writer.release()
    data = path.read_bytes()
    path.unlink()
    return data


def jpeg_data_uri() -> str:
    ok, buffer = cv2.imencode(".jpg", np.full((48, 48, 3), 120, dtype=np.uint8))
    assert ok
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def wait_for_status(client, task_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        stats = client.get(f"/api/video/stats/{task_id}").json()
        if stats["status"] in ("completed", "error"):
            return stats
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} never finished: {stats}")


def basic(password: str) -> dict:
    token = base64.b64encode(f"operator:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# --- Authentication -----------------------------------------------------------

def test_no_password_allows_access(client):
    assert client.get("/api/models").status_code == 200


def test_password_blocks_anonymous(client, monkeypatch):
    monkeypatch.setenv("ANTI_DRONE_PASSWORD", "s3cret")
    response = client.get("/api/models")
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic")
    assert client.get("/").status_code == 401
    assert client.get("/static/js/app.js").status_code == 401


def test_password_accepts_basic_and_sets_cookie(client, monkeypatch):
    monkeypatch.setenv("ANTI_DRONE_PASSWORD", "s3cret")
    response = client.get("/api/models", headers=basic("s3cret"))
    assert response.status_code == 200
    assert "anti_drone_session" in response.cookies
    # The cookie alone is enough afterwards.
    assert client.get("/api/models").status_code == 200


def test_wrong_password_rejected(client, monkeypatch):
    monkeypatch.setenv("ANTI_DRONE_PASSWORD", "s3cret")
    assert client.get("/api/models", headers=basic("wrong")).status_code == 401
    client.cookies.set("anti_drone_session", "forged")
    assert client.get("/api/models").status_code == 401


def test_websocket_rejected_without_credentials(client, monkeypatch):
    monkeypatch.setenv("ANTI_DRONE_PASSWORD", "s3cret")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/webcam"):
            pass


def test_websocket_accepted_with_session_cookie(client, monkeypatch):
    monkeypatch.setenv("ANTI_DRONE_PASSWORD", "s3cret")
    assert client.get("/", headers=basic("s3cret")).status_code == 200
    with client.websocket_connect("/ws/webcam") as websocket:
        websocket.send_text(jpeg_data_uri())
        assert "stats" in websocket.receive_json()


# --- Upload limits ------------------------------------------------------------

def test_upload_rejects_unsupported_extension(client):
    response = client.post("/api/video/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400


def test_upload_rejects_empty_file(client, app_module):
    response = client.post("/api/video/upload", files={"file": ("empty.mp4", b"", "video/mp4")})
    assert response.status_code == 400
    assert list(app_module.TMP_DIR.iterdir()) == []
    assert app_module.video_tasks == {}


def test_upload_rejects_oversize_and_cleans_up(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "MAX_UPLOAD_SIZE_BYTES", 1024)
    monkeypatch.setattr(app_module, "UPLOAD_CHUNK_BYTES", 4096)
    # Slightly over the limit: passes the Content-Length pre-check, so the
    # streaming check is what must reject it.
    response = client.post("/api/video/upload", files={"file": ("big.mp4", b"x" * 1100, "video/mp4")})
    assert response.status_code == 413
    assert list(app_module.TMP_DIR.iterdir()) == []
    assert app_module.video_tasks == {}
    # Far over the limit: refused from the declared length alone.
    response = client.post("/api/video/upload", files={"file": ("huge.mp4", b"x" * 8000, "video/mp4")})
    assert response.status_code == 413


def test_upload_rejects_when_too_many_tasks(client, app_module, monkeypatch):
    monkeypatch.setenv("ANTI_DRONE_MAX_VIDEO_TASKS", "1")
    app_module.video_tasks["busy"] = {"status": "processing"}
    response = client.post("/api/video/upload", files={"file": ("clip.mp4", b"data", "video/mp4")})
    assert response.status_code == 429


def test_prune_removes_expired_task_and_files(app_module, monkeypatch):
    monkeypatch.setenv("ANTI_DRONE_VIDEO_TTL_SECONDS", "60")
    now = time.time()
    tmp = app_module.TMP_DIR
    for name in ("old_in.mp4", "old_out.mp4", "orphan_out.mp4", "fresh_out.mp4", "busy_in.mp4"):
        (tmp / name).write_bytes(b"x")
    for name in ("old_in.mp4", "old_out.mp4", "orphan_out.mp4", "busy_in.mp4"):
        os.utime(tmp / name, (now - 600, now - 600))
    app_module.video_tasks.update({
        "old": {"status": "completed", "finished_at": now - 600},
        "fresh": {"status": "completed", "finished_at": now},
        "busy": {"status": "processing"},
    })

    app_module.prune_video_tasks(now)

    assert set(app_module.video_tasks) == {"fresh", "busy"}
    assert sorted(path.name for path in tmp.iterdir()) == ["busy_in.mp4", "fresh_out.mp4"]


# --- Video task lifecycle -----------------------------------------------------

def test_invalid_video_content_ends_in_error_status(client):
    response = client.post("/api/video/upload", files={"file": ("fake.mp4", b"not a video", "video/mp4")})
    assert response.status_code == 200
    stats = wait_for_status(client, response.json()["task_id"])
    assert stats["status"] == "error"
    assert stats["message"]


def test_predict_exception_ends_in_error_status(client, app_module, tmp_path):
    app_module.manager.fail_predict = True
    response = client.post(
        "/api/video/upload", files={"file": ("clip.mp4", make_video_bytes(tmp_path), "video/mp4")}
    )
    task_id = response.json()["task_id"]
    stats = wait_for_status(client, task_id)
    assert stats["status"] == "error"
    assert "inference exploded" in stats["message"]
    # The MJPEG stream must terminate instead of looping forever.
    assert client.get(f"/api/video/stream/{task_id}").status_code == 200
    assert client.get(f"/api/video/download/{task_id}").status_code == 404


def test_valid_video_completes_and_is_downloadable(client, tmp_path):
    response = client.post(
        "/api/video/upload", files={"file": ("clip.mp4", make_video_bytes(tmp_path), "video/mp4")}
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]
    assert len(task_id) == 32
    stats = wait_for_status(client, task_id)
    assert stats["status"] == "completed"
    assert stats["processed_frames"] == 5
    assert stats["unique_track_ids"] == [1]
    assert stats["detection_observations"] == 5
    download = client.get(f"/api/video/download/{task_id}")
    assert download.status_code == 200
    assert len(download.content) > 0


def test_stats_unknown_task_returns_404(client):
    assert client.get("/api/video/stats/nope").status_code == 404
    assert client.get("/api/video/stream/nope").status_code == 404
    assert client.get("/api/video/download/nope").status_code == 404


def test_stats_is_safe_during_processing(client, tmp_path):
    response = client.post(
        "/api/video/upload",
        files={"file": ("clip.mp4", make_video_bytes(tmp_path, frames=30), "video/mp4")},
    )
    task_id = response.json()["task_id"]
    for _ in range(200):
        stats_response = client.get(f"/api/video/stats/{task_id}")
        assert stats_response.status_code == 200
        if stats_response.json()["status"] in ("completed", "error"):
            break
    assert wait_for_status(client, task_id)["status"] == "completed"


# --- Models and inference -----------------------------------------------------

def test_switch_unknown_model_returns_404(client):
    response = client.post("/api/models/switch", data={"model_name": "../../etc/passwd"})
    assert response.status_code == 404
    assert response.json()["status"] == "error"


def test_switch_success(client):
    response = client.post("/api/models/switch", data={"model_name": "model-b.pt"})
    assert response.status_code == 200
    assert client.get("/api/models").json()["active"] == "model-b.pt"


def test_endpoints_return_503_without_manager(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "manager", None)
    assert client.get("/api/models").json() == {"models": [], "active": None}
    assert client.post("/api/models/switch", data={"model_name": "model-a.pt"}).status_code == 503
    assert client.post("/api/detect", files={"file": ("a.jpg", b"x", "image/jpeg")}).status_code == 503
    assert client.post("/api/video/upload", files={"file": ("a.mp4", b"x", "video/mp4")}).status_code == 503
    with client.websocket_connect("/ws/webcam") as websocket:
        assert "error" in websocket.receive_json()


def test_detect_returns_detections(client):
    ok, buffer = cv2.imencode(".jpg", np.full((64, 64, 3), 90, dtype=np.uint8))
    assert ok
    files = {"file": ("frame.jpg", buffer.tobytes(), "image/jpeg")}
    first = client.post("/api/detect", files=files).json()
    second = client.post("/api/detect", files=files).json()
    assert first["total_detections"] == 1
    assert first["image"].startswith("data:image/jpeg;base64,")
    # Each still image gets its own tracker, so IDs restart instead of leaking.
    assert first["track_ids"] == second["track_ids"] == [1]
    assert client.post("/api/detect", files={"file": ("bad.jpg", b"junk", "image/jpeg")}).status_code == 400
    assert client.post("/api/detect", files={"file": ("empty.jpg", b"", "image/jpeg")}).status_code == 400


def test_webcam_skips_malformed_frame(client):
    with client.websocket_connect("/ws/webcam") as websocket:
        websocket.send_text("data:image/jpeg;base64")  # no comma
        websocket.send_text("data:image/jpeg;base64,%%%not-base64%%%")
        websocket.send_text("data:image/jpeg;base64,")  # empty payload
        websocket.send_text(jpeg_data_uri())
        message = websocket.receive_json()
        assert message["stats"]["total_detections"] == 1
        assert message["stats"]["track_ids"] == [1]
