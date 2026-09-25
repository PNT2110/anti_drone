from scripts.benchmark_tracking import run


def test_tracking_benchmark_resets_at_sequence_boundary():
    records = [
        {"sequence_id": "a", "frame_id": 1, "timestamp": 0.0, "detections": [{"bbox": [0, 0, 20, 20], "confidence": 0.8}]},
        {"sequence_id": "a", "frame_id": 2, "timestamp": 0.1, "detections": [{"bbox": [1, 0, 21, 20], "confidence": 0.8}]},
        {"sequence_id": "b", "frame_id": 1, "timestamp": 0.0, "detections": [{"bbox": [100, 100, 120, 120], "confidence": 0.8}]},
    ]
    result = run("bytetrack_motion_adaptive", records, drop_every=0)
    assert result["status"] == "DONE"
    assert result["sequences_processed"] == 2
    assert result["sequence_resets"] == 1
    assert result["tracks_created"] == 2
