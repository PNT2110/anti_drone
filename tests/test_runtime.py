import numpy as np
import pytest

pytest.importorskip("cv2")

from anti_drone.alerts import TemporalAlert
from anti_drone.runtime import AlertState, Detection, ByteTrackLite, DetectorPipeline, decode_yolo_output, letterbox
from anti_drone.tracking import ByteTrack, ByteTrackConfig


def test_letterbox_preserves_shape_contract():
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    canvas, scale, pad = letterbox(image, 640)
    assert canvas.shape == (640, 640, 3)
    assert round(scale, 6) == round(0.5, 6)
    assert pad == (0.0, 140.0)


def test_decode_one_class_output_and_restore():
    raw = np.zeros((1, 5, 1), dtype=np.float32)
    raw[0, :, 0] = [320, 320, 100, 80, 0.9]
    detections = decode_yolo_output(raw, (720, 1280), 0.5, (0.0, 140.0), confidence=0.25, nms_iou=0.7)
    assert len(detections) == 1
    assert np.allclose(detections[0].box, [540, 280, 740, 440], atol=1)


def test_alert_requires_three_hits():
    tracker = ByteTrackLite(high_threshold=0.25, match_iou=0.2)
    alert = AlertState(confirm_hits=3, confirm_window=5, cooldown_frames=30)
    detections = [Detection(np.array([10, 10, 50, 50], dtype=np.float32), 0.8)]
    assert alert.update(tracker.update(detections, 1), 1) == []
    assert alert.update(tracker.update(detections, 2), 2) == []
    assert len(alert.update(tracker.update(detections, 3), 3)) == 1


def test_nms_receives_xywh_and_keeps_valid_box(monkeypatch):
    calls = {}

    def fake_nms(boxes, scores, score_threshold, nms_threshold):
        calls["boxes"] = boxes
        calls["scores"] = scores
        return np.array([[0]], dtype=np.int32)

    monkeypatch.setattr("cv2.dnn.NMSBoxes", fake_nms)
    raw = np.zeros((1, 5, 2), dtype=np.float32)
    raw[0, :, 0] = [320, 320, 100, 80, 0.9]
    raw[0, :, 1] = [320, 320, 90, 70, 0.8]
    detections = decode_yolo_output(raw, (640, 640), 1.0, (0.0, 0.0), confidence=0.1, nms_iou=0.7)
    assert calls["boxes"][0] == [270.0, 280.0, 100.0, 80.0]
    assert len(detections) == 1


def test_decoder_rejects_empty_zero_area_and_non_finite_boxes():
    raw = np.array([[[10.0, np.nan, 20.0], [10.0, 10.0, 20.0], [0.0, 4.0, 20.0], [10.0, 4.0, 0.0], [0.9, 0.9, 0.9]]], dtype=np.float32)
    assert decode_yolo_output(raw, (100, 100), 1.0, (0.0, 0.0), confidence=0.1) == []


def test_pipeline_reset_clears_tracker_and_alert_session():
    pipeline = DetectorPipeline.__new__(DetectorPipeline)
    pipeline.tracker = ByteTrack(ByteTrackConfig())
    pipeline.alerts = TemporalAlert()
    pipeline.last_alert_events = []
    pipeline.max_gap_before_reset_seconds = 1.0
    pipeline._last_timestamp = 4.0
    old_session = pipeline.alerts.session_id
    pipeline.reset()
    assert pipeline.tracker.next_id == 1
    assert pipeline.alerts.session_id != old_session
    assert pipeline.alerts.history == {}
    assert pipeline._last_timestamp is None
