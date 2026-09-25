import dataclasses
import json
from pathlib import Path

import numpy as np

from anti_drone.tracking import ByteTrackConfig, Detection
from anti_drone.tracking.types import Track
from scripts.run_scope08_audit import TraceAlert, TraceMotion, load_inputs
from scripts.run_scope09_gate_sensitivity import compare_tracker_rows, sha256


ROOT = Path(__file__).resolve().parents[1]


def _observed_track(source_frame=10):
    box = np.asarray([0, 0, 10, 10], dtype=np.float32)
    return Track(
        track_id=1,
        bbox_observed=box.copy(),
        bbox_predicted=box.copy(),
        confidence=0.8,
        matched_this_frame=True,
        last_observed_at=source_frame / 30,
        observation_count=1,
        high_confidence_observations=1,
        hits=1,
        last_frame=source_frame,
        last_source_frame=source_frame,
    )


def test_scope09_default_config_is_unchanged_and_override_only_changes_gate():
    default = dataclasses.asdict(ByteTrackConfig())
    override = dataclasses.asdict(ByteTrackConfig(adaptive_mahalanobis_gate=16.0))
    assert default["adaptive_mahalanobis_gate"] == 25.0
    assert [key for key in default if default[key] != override[key]] == ["adaptive_mahalanobis_gate"]


def test_scope09_tracker_reset_restarts_experiment_state():
    tracker = TraceMotion(ByteTrackConfig(adaptive_mahalanobis_gate=16.0), mode="motion")
    detection = [Detection(np.asarray([0, 0, 10, 10], dtype=np.float32), 0.8)]
    first = tracker.update(detection, timestamp=0.0, frame_id=1, source_frame_id=1)
    tracker.reset()
    second = tracker.update(detection, timestamp=0.0, frame_id=1, source_frame_id=1)
    assert first[0].track_id == 1
    assert second[0].track_id == 1


def test_scope09_cache_and_inputs_are_read_only():
    manifest = ROOT / "data/tracking_eval/sequence_001/frame_manifest.csv"
    ground_truth = ROOT / "data/tracking_eval/sequence_001/annotations/ground_truth.csv"
    cache = ROOT / "data/tracking_eval/sequence_001/detection_cache.onnx.jsonl"
    validation = ROOT / "data/tracking_eval/sequence_001/review/identity_review_validation.json"
    before = sha256(cache)
    records, gt_by_frame = load_inputs(manifest, ground_truth, cache, validation)
    after = sha256(cache)
    assert len(records) == 301
    assert len(gt_by_frame) == 301
    assert before == after


def test_scope09_prediction_only_alert_is_inert():
    alert = TraceAlert(min_observations=1, min_high_confidence_observations=0, confirmation_window_seconds=1.0, cooldown_seconds=2.0)
    track = _observed_track()
    track.bbox_observed = None
    track.matched_this_frame = False
    _, events = alert.update([track], timestamp=4.0, source_frame_id=10)
    assert events == []
    assert alert.history == {}


def test_scope09_baseline_gate25_reproduces_scope08():
    runtime = ROOT / ".runtime"
    for profile in ("bytetrack_motion", "bytetrack_motion_adaptive"):
        current = [json.loads(line) for line in (runtime / "scope09" / f"{profile}_gate25.jsonl").read_text().splitlines()]
        baseline = [json.loads(line) for line in (runtime / "scope08" / f"{profile}.jsonl").read_text().splitlines()]
        comparison = compare_tracker_rows(current, baseline)
        assert comparison["status"] == "PASS"
        assert comparison["frames_compared"] == 301


def test_scope09_results_have_all_declared_profiles_and_gates():
    report = json.loads((ROOT / ".runtime/scope09/SCOPE09_RESULTS.json").read_text())
    assert report["status"] == "PASS"
    assert {(item["profile"], item["gate"]) for item in report["results"]} == {
        (profile, gate)
        for profile in ("bytetrack_motion", "bytetrack_motion_adaptive")
        for gate in (16.0, 25.0, 36.0)
    }
    assert all(item["prediction_only_alerts"] == 0 for item in report["results"])
    assert all(not item["duplicate_alert_source_frames"] for item in report["results"])
