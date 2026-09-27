"""Scope 28 dual-stream contract and Pi evidence guards."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anti_drone.scope28_contract import select_single_drone_observation, split_observations, suppress_contained_duplicates  # noqa: E402
from anti_drone.tracking import ByteTrack, ByteTrackConfig, Detection  # noqa: E402


RUNTIME = ROOT / ".runtime/scope28"
FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name: str):
    return json.loads((RUNTIME / name).read_text())


def test_scope28_baselines_and_direct_contract_diagnosis():
    diagnosis = read("contract_diagnosis.json")
    assert diagnosis["status"] == "CONTRACT_GAP_CONFIDENCE_FLOOR"
    assert diagnosis["answer"] == "YES"
    assert all(diagnosis["evidence"].values())
    assert digest(ROOT / ".runtime/scope25/scope25_freeze_manifest.json") == FREEZE
    assert digest(ROOT / ".runtime/scope26/headline_result.json") == HEADLINE
    assert digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.param") == PARAM
    assert digest(ROOT / "artifacts/production-candidate/scope25/model.ncnn.bin") == BIN


def test_dual_stream_preserves_public_contract_and_low_confidence():
    rows = [
        {"class": 0, "confidence": 0.60, "bbox": [1.0, 1.0, 10.0, 10.0]},
        {"class": 0, "confidence": 0.20, "bbox": [20.0, 20.0, 30.0, 30.0]},
        {"class": 0, "confidence": 0.09, "bbox": [40.0, 40.0, 50.0, 50.0]},
    ]
    streams = split_observations(rows)
    assert streams["nms_applications"] == 1
    assert [row["confidence"] for row in streams["high"]] == [0.60]
    assert [row["confidence"] for row in streams["low"]] == [0.20]
    assert streams["low"][0]["stream"] == "TRACKER_LOW_STREAM"
    assert streams["tracker_observations"] == streams["high"] + streams["low"]


def test_low_only_detection_cannot_create_new_track():
    tracker = ByteTrack(ByteTrackConfig(), mode="motion_adaptive")
    tracks = tracker.update([Detection(box=__import__("numpy").array([10, 10, 30, 30], dtype=float), confidence=0.20, class_id=0)], timestamp=0.0, frame_id=1, source_frame_id=1)
    assert tracks == []
    assert tracker.next_id == 1


def test_contained_part_box_is_suppressed_without_second_nms():
    whole = {"class": 0, "confidence": 0.74, "bbox": [260.0, 303.0, 640.0, 480.0]}
    part = {"class": 0, "confidence": 0.55, "bbox": [408.0, 309.0, 622.0, 480.0]}
    separate = {"class": 0, "confidence": 0.45, "bbox": [10.0, 10.0, 80.0, 80.0]}
    kept, suppressed = suppress_contained_duplicates([whole, part, separate])
    assert suppressed == 1
    assert kept == [whole, separate]


def test_containment_guard_does_not_remove_nearby_separate_boxes():
    rows = [
        {"class": 0, "confidence": 0.8, "bbox": [0.0, 0.0, 100.0, 100.0]},
        {"class": 0, "confidence": 0.7, "bbox": [80.0, 0.0, 180.0, 100.0]},
    ]
    kept, suppressed = suppress_contained_duplicates(rows)
    assert suppressed == 0
    assert kept == rows


def test_crossing_part_box_is_suppressed_by_overlap_of_smaller():
    whole = {"class": 0, "confidence": 0.4453125, "bbox": [339.4167, 224.5, 640.0, 480.0]}
    part = {"class": 0, "confidence": 0.2956543, "bbox": [427.3333, 170.6667, 638.6667, 480.0]}
    kept, suppressed = suppress_contained_duplicates([whole, part])
    assert suppressed == 1
    assert kept == [whole]


def test_single_drone_mode_keeps_one_whole_high_observation():
    whole = {"class": 0, "confidence": 0.62, "bbox": [100.0, 100.0, 600.0, 470.0]}
    tight_part = {"class": 0, "confidence": 0.88, "bbox": [250.0, 180.0, 380.0, 300.0]}
    low = {"class": 0, "confidence": 0.18, "bbox": [105.0, 105.0, 595.0, 465.0]}
    high_kept, low_kept, suppressed = select_single_drone_observation([whole, tight_part], [low])
    assert high_kept == [whole]
    assert low_kept == []
    assert suppressed == 2


def test_single_drone_mode_uses_one_low_only_when_no_high_exists():
    best = {"class": 0, "confidence": 0.20, "bbox": [10.0, 10.0, 200.0, 200.0]}
    part = {"class": 0, "confidence": 0.22, "bbox": [20.0, 20.0, 70.0, 70.0]}
    high_kept, low_kept, suppressed = select_single_drone_observation([], [best, part])
    assert high_kept == []
    assert low_kept == [best]
    assert suppressed == 1


def test_single_drone_selector_honors_user_point_and_fails_closed_when_point_misses():
    high = [
        {"class": 0, "confidence": 0.80, "bbox": [0.0, 400.0, 500.0, 700.0]},
        {"class": 0, "confidence": 0.55, "bbox": [700.0, 0.0, 1270.0, 350.0]},
    ]
    selected, low, suppressed = select_single_drone_observation(high, [], preferred_point=(1000.0, 80.0))
    assert selected == [high[1]]
    assert low == []
    assert suppressed == 1
    selected, low, suppressed = select_single_drone_observation(high, [], preferred_point=(650.0, 360.0))
    assert selected == []
    assert low == []
    assert suppressed == 2


def test_pi_halmstad_dual_run_and_high_equivalence():
    summary = read("summary.json")
    parity = read("parity_8.json")
    assert summary["status"] == "DRY_RUN_COMPLETE"
    assert summary["frames_expected"] == summary["frames_processed"] == 301
    assert parity["status"] == "PARITY_PASS"
    assert len(parity["images"]) == 8
    assert all(row["parity"]["status"] == "PARITY_PASS" for row in parity["images"])
    assert summary["high_stream_equivalence"] == {"frames": 301, "pass_frames": 301, "fail_frames": 0}
    assert summary["stream_aggregates"]["low_only_frames"] == 15
    assert summary["association_counts"]["LOW"] == 13
    assert summary["single_inference_per_frame"] is True
    assert summary["one_nms_per_frame"] is True
    assert summary["test_accessed"] is False


def test_scope28_safety_timestamps_and_immutable_tracker_policy():
    summary = read("summary.json")
    audit = read("input_audit.json")
    rows = [json.loads(line) for line in (RUNTIME / "target_state.jsonl").read_text().splitlines()]
    assert audit["tracker_profile"] == "bytetrack_motion_adaptive"
    assert audit["production_package_modified"] is False
    assert len(rows) == 301
    assert [row["timestamp"] for row in rows] == sorted(row["timestamp"] for row in rows)
    assert summary["events"]["COORDINATE_ERROR"]["count"] == 0
    assert summary["events"]["TIMESTAMP_ERROR"]["count"] == 0
    assert summary["actuator"] == {"mode": "DRY_RUN_ONLY", "enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0}
    assert all(row["command_preview"]["actuator_output_enabled"] is False for row in rows)
    assert all(row["command_preview"]["gpio_write"] is False for row in rows)
    assert all(row["command_preview"]["pwm_write"] is False for row in rows)
    assert all(row["command_preview"]["serial_write"] is False for row in rows)
