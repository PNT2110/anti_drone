"""Fixtures that exercise the real web/app.py with a fake inference manager."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pytest

WEB_DIR = Path(__file__).resolve().parents[1]
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

# The API tests never run a neural model, so they must not require the
# ultralytics/torch stack. A real installation is used untouched when present.
try:
    import ultralytics  # noqa: F401
except ImportError:
    sys.modules["ultralytics"] = types.ModuleType("ultralytics")


class FakeManager:
    """Stands in for ModelManager: one fixed detection per frame."""

    def __init__(self) -> None:
        self.active = "model-a.pt"
        self.fail_predict = False
        self.predict_calls = 0

    def list_models(self) -> list[dict]:
        return [
            {"name": name, "label": name.upper(), "is_active": name == self.active}
            for name in ("model-a.pt", "model-b.pt")
        ]

    def set_active_model(self, model_name: str) -> bool:
        if model_name not in ("model-a.pt", "model-b.pt"):
            raise KeyError(model_name)
        self.active = model_name
        return True

    def predict(self, image, tracker=None, timestamp=None, **_kwargs):
        from backend.detector import DetectionResult

        self.predict_calls += 1
        if self.fail_predict:
            raise RuntimeError("inference exploded")
        boxes = [[10.0, 10.0, 40.0, 40.0]]
        confidences = [0.9]
        track_ids = [None]
        if tracker is not None:
            track_ids = tracker.update(image, boxes, confidences, timestamp or 0.0)
        return DetectionResult(
            boxes=boxes,
            confidences=confidences,
            class_ids=[0],
            class_names=["drone"],
            track_ids=track_ids,
            annotated_frame=np.ascontiguousarray(image).copy(),
        )


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    import app

    monkeypatch.delenv("ANTI_DRONE_PASSWORD", raising=False)
    monkeypatch.setattr(app, "manager", FakeManager())
    monkeypatch.setattr(app, "TMP_DIR", tmp_path)
    with app.video_tasks_lock:
        app.video_tasks.clear()
    yield app
    with app.video_tasks_lock:
        app.video_tasks.clear()


@pytest.fixture
def client(app_module):
    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as test_client:
        yield test_client
