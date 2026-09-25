import csv
import json

import numpy as np

from anti_drone.tracking import ByteTrack, ByteTrackConfig, Detection
from anti_drone.tracking.types import Track
from scripts.run_scope08_audit import (
    TraceAlert,
    TraceMotion,
    load_inputs,
    switch_events,
    verify_expected_checksums,
)


def observed_track(track_id=1, source_frame=1, confidence=0.8):
    box = np.asarray([0, 0, 10, 10], dtype=np.float32)
    return Track(
        track_id=track_id,
        bbox_observed=box.copy(),
        bbox_predicted=box.copy(),
        confidence=confidence,
        matched_this_frame=True,
        last_observed_at=source_frame / 30,
        observation_count=1,
        high_confidence_observations=1,
        hits=1,
        last_frame=source_frame,
        last_source_frame=source_frame,
    )


def test_alert_trace_keeps_event_frame_and_source_frame_distinct():
    alert = TraceAlert(min_observations=1, min_high_confidence_observations=0, confirmation_window_seconds=1.0, cooldown_seconds=2.0)
    _, events = alert.update([observed_track(source_frame=10)], timestamp=4.0, source_frame_id=10)
    assert len(events) == 1
    event = alert.last_trace["events"][0]
    assert event["creation_frame"] == 10
    assert event["source_frame_id"] == 10
    assert event["timestamp"] == 4.0


def test_prediction_only_does_not_create_alert_observation():
    alert = TraceAlert(min_observations=1, min_high_confidence_observations=0, confirmation_window_seconds=1.0, cooldown_seconds=2.0)
    track = observed_track(source_frame=10)
    track.bbox_observed = None
    track.matched_this_frame = False
    _, events = alert.update([track], timestamp=4.0, source_frame_id=10)
    assert events == []
    assert alert.history == {}
    assert alert.last_trace["tracks"][0]["reason"] == "prediction_only_skip"


def test_duplicate_source_frame_does_not_create_duplicate_observation():
    alert = TraceAlert(min_observations=1, min_high_confidence_observations=0, confirmation_window_seconds=1.0, cooldown_seconds=2.0)
    track = observed_track(source_frame=10)
    _, first_events = alert.update([track], timestamp=4.0, source_frame_id=10)
    _, second_events = alert.update([track], timestamp=4.1, source_frame_id=10)
    assert len(first_events) == 1
    assert second_events == []
    assert len(alert.history[1]) == 1
    assert alert.last_trace["tracks"][0]["reason"] == "duplicate_source_frame_skip"


def test_id_switch_trace_preserves_frame_order():
    rows = [
        {
            "frame_id": 1,
            "gt_matched_track_id": 1,
            "tracks": [{"track_id": 1, "observed": True}],
            "tracks_before": [],
            "association": [],
            "lifecycle_events": [],
        },
        {
            "frame_id": 2,
            "gt_matched_track_id": 2,
            "tracks": [{"track_id": 2, "observed": True}],
            "tracks_before": [{"track_id": 1}],
            "association": [{"track_id": 1, "gate_pass": False, "rejection_reason": "iou_below_match_iou"}],
            "lifecycle_events": [{"event": "created", "track_id": 2, "reason": "new_track_from_unmatched_eligible_detection"}],
        },
    ]
    events = switch_events(rows)
    assert [(event["from_frame"], event["switch_frame"]) for event in events] == [(1, 2)]
    assert events[0]["classification"] == "C_ASSOCIATION_GATE_REJECTED"


def test_sequence_reset_does_not_carry_track_id():
    tracker = TraceMotion(ByteTrackConfig(), mode="motion")
    detection = [Detection(np.asarray([0, 0, 10, 10], dtype=np.float32), 0.8)]
    first = tracker.update(detection, timestamp=0.0, frame_id=1, source_frame_id=1)
    tracker.reset()
    second = tracker.update(detection, timestamp=0.0, frame_id=1, source_frame_id=1)
    assert first[0].track_id == 1
    assert second[0].track_id == 1


def test_instrumentation_does_not_change_motion_tracker_output():
    traced = TraceMotion(ByteTrackConfig(), mode="motion_adaptive")
    baseline = ByteTrack(ByteTrackConfig(), mode="motion_adaptive")
    for frame_id, box in ((1, [0, 0, 10, 10]), (2, [1, 0, 11, 10]), (3, [2, 0, 12, 10])):
        detection = [Detection(np.asarray(box, dtype=np.float32), 0.8)]
        traced_tracks = traced.update(detection, timestamp=frame_id / 30, frame_id=frame_id, source_frame_id=frame_id)
        baseline_tracks = baseline.update(detection, timestamp=frame_id / 30, frame_id=frame_id, source_frame_id=frame_id)
        assert [(track.track_id, track.is_observed, track.state) for track in traced_tracks] == [(track.track_id, track.is_observed, track.state) for track in baseline_tracks]
        assert np.allclose(traced_tracks[0].bbox, baseline_tracks[0].bbox)


def test_input_audit_detects_checksum_mismatch():
    errors = verify_expected_checksums(
        {"manifest": "expected", "tracker_configs": {"bytetrack_motion": "config-hash"}},
        {"manifest": "changed", "tracker_configs": {"bytetrack_motion": "config-hash"}},
    )
    assert any("checksum mismatch for manifest" in error for error in errors)


def test_input_audit_detects_frame_mismatch(tmp_path):
    manifest = tmp_path / "manifest.csv"
    ground_truth = tmp_path / "ground_truth.csv"
    cache = tmp_path / "cache.jsonl"
    validation = tmp_path / "validation.json"
    manifest_fields = ["sequence_id", "frame_id", "timestamp"]
    gt_fields = ["sequence_id", "frame_id", "track_id", "class_id", "x1", "y1", "x2", "y2"]
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=manifest_fields)
        writer.writeheader()
        for frame_id in range(1, 302):
            writer.writerow({"sequence_id": "halmstad_v_drone_001", "frame_id": frame_id, "timestamp": frame_id / 30})
    with ground_truth.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=gt_fields)
        writer.writeheader()
        for frame_id in range(1, 302):
            writer.writerow({"sequence_id": "halmstad_v_drone_001", "frame_id": frame_id, "track_id": 1, "class_id": 0, "x1": 0, "y1": 0, "x2": 10, "y2": 10})
    with cache.open("w", encoding="utf-8") as handle:
        for frame_id in range(1, 302):
            cache_frame = 300 if frame_id == 301 else frame_id
            handle.write(json.dumps({"sequence_id": "halmstad_v_drone_001", "frame_id": cache_frame, "timestamp": frame_id / 30, "detections": []}) + "\n")
    validation.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    try:
        load_inputs(manifest, ground_truth, cache, validation)
    except RuntimeError as exc:
        assert "cache frame order mismatch" in str(exc)
    else:
        raise AssertionError("frame mismatch was not detected")
