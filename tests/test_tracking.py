import numpy as np
import pytest

from anti_drone.alerts import TemporalAlert
from anti_drone.tracking import ByteTrack, ByteTrackConfig, ByteTrackLegacy, Detection, TrackState


def det(box, confidence=0.8):
    return Detection(np.asarray(box, dtype=np.float32), confidence)


def tracker(mode="motion_adaptive", **kwargs):
    config = ByteTrackConfig(**kwargs)
    return ByteTrack(config, mode=mode)


def test_high_low_two_stage_and_new_track_threshold():
    track = tracker()
    first = track.update([det([10, 10, 30, 30], 0.8)], timestamp=0.0, frame_id=1, source_frame_id=1)
    assert len(first) == 1 and first[0].matched_this_frame
    second = track.update([det([10, 10, 30, 30], 0.15)], timestamp=0.1, frame_id=2, source_frame_id=2)
    assert len(second) == 1
    assert second[0].track_id == first[0].track_id
    assert second[0].observation_count == 2
    assert second[0].confidence == pytest.approx(0.15)
    assert track.update([det([100, 100, 120, 120], 0.30)], timestamp=0.2, frame_id=3, source_frame_id=3)
    assert len(track.tracks) == 1, "high but below new_track_thresh must not create a track"
    assert track.update([det([100, 100, 120, 120], 0.40)], timestamp=0.3, frame_id=4, source_frame_id=4)
    assert len(track.tracks) == 2


def test_assignment_is_one_to_one_and_deterministic():
    config = ByteTrackConfig(match_iou=0.1, new_track_thresh=0.35)
    a = ByteTrack(config)
    b = ByteTrack(config)
    inputs = [det([0, 0, 20, 20], 0.8), det([50, 0, 70, 20], 0.8)]
    assert [t.track_id for t in a.update(inputs, 0.0, 1, 1)] == [1, 2]
    assert [t.track_id for t in b.update(inputs, 0.0, 1, 1)] == [1, 2]
    next_inputs = [det([1, 0, 21, 20], 0.8), det([49, 0, 69, 20], 0.8)]
    a_tracks = a.update(next_inputs, 0.1, 2, 2)
    b_tracks = b.update(next_inputs, 0.1, 2, 2)
    assert [(t.track_id, t.observation_count) for t in a_tracks] == [(t.track_id, t.observation_count) for t in b_tracks]
    assert {t.track_id for t in a_tracks if t.matched_this_frame} == {1, 2}


def test_two_tracks_competing_for_one_detection_match_only_once():
    track = tracker()
    initial = track.update([det([0, 0, 20, 20]), det([5, 0, 25, 20])], 0.0, 1, 1)
    assert len(initial) == 2
    current = track.update([det([4, 0, 24, 20])], 0.1, 2, 2)
    assert sum(item.matched_this_frame for item in current) == 1
    assert len({item.track_id for item in current}) == 2


def test_actual_dt_drives_prediction_and_dropped_frame_gap():
    short_gap = tracker()
    long_gap = tracker()
    for current in (short_gap, long_gap):
        current.update([det([0, 0, 10, 10])], 0.0, 1, 1)
        current.update([det([10, 0, 20, 10])], 0.1, 2, 2)
    short_prediction = short_gap.update([], 0.2, 3, 3)[0]
    predicted = long_gap.update([], 0.5, 3, 3)
    assert predicted and predicted[0].state == TrackState.LOST
    assert predicted[0].box[0] > short_prediction.box[0]
    assert predicted[0].missed_seconds == pytest.approx(0.4)


def test_adaptive_mode_recovers_small_object_when_iou_is_zero():
    fixed = tracker(mode="motion", match_iou=0.3)
    adaptive = tracker(mode="motion_adaptive", match_iou=0.3)
    for current in (fixed, adaptive):
        current.update([det([10, 10, 14, 14])], 0.0, 1, 1)
    fixed_tracks = fixed.update([det([14, 10, 18, 14])], 0.1, 2, 2)
    adaptive_tracks = adaptive.update([det([14, 10, 18, 14])], 0.1, 2, 2)
    assert fixed_tracks[0].observation_count == 1
    assert adaptive_tracks[0].observation_count == 2


def test_lifecycle_timeout_uses_seconds_not_frame_count():
    track = tracker(max_lost_seconds=0.6, max_gap_before_reset_seconds=1.0)
    track.update([det([0, 0, 20, 20])], 0.0, 1, 1)
    assert track.update([], 0.5, 2, 2)[0].state == TrackState.LOST
    assert track.update([], 0.7, 3, 3) == []


def test_temporal_alert_ignores_prediction_and_deduplicates_source_frame():
    track = tracker()
    alert = TemporalAlert(min_observations=3, min_high_confidence_observations=2, confirmation_window_seconds=1.0, cooldown_seconds=2.0)
    for timestamp, source in ((0.0, 1), (0.1, 2)):
        _, events = alert.update(track.update([det([0, 0, 20, 20])], timestamp, int(source), source), timestamp)
        assert events == []
    _, events = alert.update(track.update([], 0.2, 3, 3), 0.2)
    assert events == []
    duplicate_track = track.update([det([0, 0, 20, 20])], 0.3, 4, 2)[0]
    assert duplicate_track.observation_count == 2
    _, duplicate_events = alert.update([duplicate_track], 0.3)
    assert duplicate_events == [], "replayed source frame must not count twice"
    _, events = alert.update(track.update([det([0, 0, 20, 20])], 0.4, 5, 4), 0.4)
    assert len(events) == 1


def test_alert_cooldown_is_independent_per_track():
    track = tracker()
    alert = TemporalAlert(min_observations=1, min_high_confidence_observations=1, confirmation_window_seconds=1.0, cooldown_seconds=2.0)
    first_tracks = track.update([det([0, 0, 20, 20])], 0.0, 1, 1)
    _, first_events = alert.update(first_tracks, 0.0)
    assert [event.track_id for event in first_events] == [1]
    second_tracks = track.update([det([100, 100, 120, 120])], 1.0, 2, 2)
    _, second_events = alert.update(second_tracks, 1.0)
    assert [event.track_id for event in second_events] == [2]


def test_timestamp_validation_reset_empty_and_invalid_inputs():
    track = tracker()
    assert track.update([], 0.0, 1, 1) == []
    with pytest.raises(ValueError):
        track.update([], -1.0, 2, 2)
    assert track.update([det([0, 0, 10, 10], float("nan"))], 0.1, 3, 3) == []
    track.reset()
    assert track.next_id == 1 and track.update([], 0.0, 1, 1) == []


def test_long_timestamp_gap_starts_a_fresh_session():
    track = tracker(max_lost_seconds=10.0, max_gap_before_reset_seconds=1.0)
    assert track.update([det([0, 0, 10, 10])], 0.0, 1, 1)[0].track_id == 1
    assert track.update([det([100, 100, 110, 110])], 2.0, 2, 2)[0].track_id == 1


def test_legacy_tracker_remains_usable_with_original_positional_api():
    legacy = ByteTrackLegacy(high_threshold=0.25, match_iou=0.2)
    detections = [det([10, 10, 50, 50])]
    assert legacy.update(detections, 1)[0].matched_this_frame
    assert legacy.update(detections, 2)[0].observation_count == 2
