import numpy as np

from anti_drone.runtime import AlertState, Detection, ByteTrackLite, decode_yolo_output, letterbox


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
