from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np

WEB_DIR = Path(__file__).resolve().parents[1]
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

_TRACKER_SPEC = importlib.util.spec_from_file_location(
    "tracker_under_test", WEB_DIR / "backend" / "tracker.py"
)
assert _TRACKER_SPEC is not None and _TRACKER_SPEC.loader is not None
_TRACKER_MODULE = importlib.util.module_from_spec(_TRACKER_SPEC)
sys.modules["tracker_under_test"] = _TRACKER_MODULE
_TRACKER_SPEC.loader.exec_module(_TRACKER_MODULE)
IdentityTracker = _TRACKER_MODULE.IdentityTracker
_appearance_distance = _TRACKER_MODULE._appearance_distance
_descriptor = _TRACKER_MODULE._descriptor


def _frame(x: int = 25, color: tuple[int, int, int] = (40, 180, 230)) -> np.ndarray:
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    # A textured, colored crop gives the appearance gallery a deterministic
    # fingerprint while avoiding a detector/model dependency in this test.
    cv2.rectangle(image, (x, 70), (x + 60, 130), color, -1)
    cv2.line(image, (x + 5, 75), (x + 55, 125), (255, 255, 255), 3)
    cv2.circle(image, (x + 30, 100), 12, (20, 20, 80), -1)
    return image


def _two_drone_frame(x_by_id: dict[int, int]) -> tuple[np.ndarray, dict[int, list[int]]]:
    image = np.zeros((220, 320, 3), dtype=np.uint8)
    boxes = {}
    appearances = {
        1: ((40, 180, 230), (255, 255, 255)),
        2: ((220, 80, 35), (30, 255, 255)),
    }
    for drone_id, x in x_by_id.items():
        color, detail = appearances[drone_id]
        box = [x, 80, x + 48, 128]
        boxes[drone_id] = box
        cv2.rectangle(image, (x, 80), (x + 48, 128), color, -1)
        cv2.line(image, (x + 4, 84), (x + 44, 124), detail, 4)
        cv2.circle(image, (x + 24, 104), 9, (20, 20, 80), -1)
    return image, boxes


def _small_drone_frame(x: int, width: int = 320) -> tuple[np.ndarray, list[int]]:
    image = np.zeros((160, width, 3), dtype=np.uint8)
    box = [x, 65, x + 24, 89]
    cv2.rectangle(image, (x, 65), (x + 24, 89), (40, 180, 230), -1)
    cv2.line(image, (x + 2, 67), (x + 22, 87), (255, 255, 255), 2)
    cv2.circle(image, (x + 12, 77), 4, (20, 20, 80), -1)
    return image, box


def _small_drone_frame_at(*xs: int) -> tuple[np.ndarray, list[list[int]]]:
    image = np.zeros((160, 320, 3), dtype=np.uint8)
    boxes = []
    for x in xs:
        box = [x, 65, x + 24, 89]
        boxes.append(box)
        cv2.rectangle(image, (x, 65), (x + 24, 89), (40, 180, 230), -1)
        cv2.line(image, (x + 2, 67), (x + 22, 87), (255, 255, 255), 2)
        cv2.circle(image, (x + 12, 77), 4, (20, 20, 80), -1)
    return image, boxes


def test_id_survives_long_reentry_with_same_appearance() -> None:
    tracker = IdentityTracker(max_lost_seconds=2.0, reid_memory_seconds=30.0)
    frame = _frame()
    first = tracker.update(frame, [[25, 70, 85, 130]], [0.95], 0.0)
    assert first == [1]

    # No detection for ten seconds: the old ID must stay in the dormant gallery.
    tracker.update(frame, [], [], 10.0)
    returned = tracker.update(_frame(220), [[220, 70, 280, 130]], [0.93], 10.1)
    assert returned == [1]


def test_appearance_match_can_reidentify_far_from_stale_position() -> None:
    tracker = IdentityTracker(
        max_lost_seconds=2.0,
        reid_memory_seconds=30.0,
        reid_center_gate=4.0,
    )
    first_frame, first_box = _small_drone_frame(15)
    assert tracker.update(first_frame, [first_box], [0.95], 0.0) == [1]

    # After a long gap the old position is no longer a meaningful gate: the
    # drone can re-enter at the opposite side of the image. Its clear visual
    # match should recover ID 1 instead of creating a duplicate identity.
    tracker.update(first_frame, [], [], 10.0)
    returned_frame, returned_box = _small_drone_frame(275)
    assert tracker.update(returned_frame, [returned_box], [0.93], 10.1) == [1]


def test_appearance_second_chance_rescues_track_inside_active_ttl() -> None:
    tracker = IdentityTracker(max_lost_seconds=4.0, reid_memory_seconds=30.0)
    first_frame, first_box = _small_drone_frame(15, width=2048)
    assert tracker.update(first_frame, [first_box], [0.95], 0.0) == [1]
    tracker.update(first_frame, [], [], 1.0)

    # Motion gating rejects this unusually large fast-flight displacement,
    # but the appearance fallback must still recover the unmatched active ID.
    returned_frame, returned_box = _small_drone_frame(1800, width=2048)
    assert tracker.update(returned_frame, [returned_box], [0.93], 1.1) == [1]


def test_ambiguous_global_reid_does_not_guess_between_lookalikes() -> None:
    tracker = IdentityTracker(max_lost_seconds=2.0, reid_memory_seconds=30.0)
    first_frame, first_boxes = _small_drone_frame_at(15, 275)
    assert tracker.update(first_frame, first_boxes, [0.95, 0.95], 0.0) == [1, 2]

    tracker.update(first_frame, [], [], 10.0)
    middle_frame, middle_box = _small_drone_frame(145)
    # The two old IDs have indistinguishable appearance and equal spatial
    # evidence. A new ID is safer than a random resurrection of ID 1 or 2.
    assert tracker.update(middle_frame, [middle_box], [0.93], 10.1) == [3]


def test_different_appearance_gets_new_id_after_long_gap() -> None:
    tracker = IdentityTracker(max_lost_seconds=2.0, reid_memory_seconds=30.0)
    first_frame = _frame()
    tracker.update(first_frame, [[25, 70, 85, 130]], [0.95], 0.0)
    tracker.update(first_frame, [], [], 10.0)
    different = np.zeros_like(first_frame)
    for row in range(70, 130, 10):
        for col in range(220, 280, 10):
            if ((row // 10) + (col // 10)) % 2:
                cv2.rectangle(different, (col, row), (col + 9, row + 9), (255, 255, 255), -1)
    returned = tracker.update(different, [[220, 70, 280, 130]], [0.93], 10.1)
    assert returned == [2]


def test_low_confidence_box_can_continue_track_without_poisoning_gallery() -> None:
    tracker = IdentityTracker(min_new_track_confidence=0.25)
    first_frame = _frame()
    assert tracker.update(first_frame, [[25, 70, 85, 130]], [0.9], 0.0) == [1]
    assert len(tracker.tracks[1].gallery) == 1

    # A weak but motion-consistent box keeps the ID visible but does not add a
    # noisy appearance sample to the long-term gallery.
    continued = tracker.update(
        _frame(27), [[27, 70, 87, 130]], [0.18], 1 / 30
    )
    assert continued == [1]
    assert len(tracker.tracks[1].gallery) == 1


def test_mismatched_active_crop_does_not_poison_identity_gallery() -> None:
    tracker = IdentityTracker(gallery_update_threshold=0.15)
    first = _frame(color=(40, 180, 230))
    assert tracker.update(first, [[25, 70, 85, 130]], [0.9], 0.0) == [1]
    assert len(tracker.tracks[1].gallery) == 1

    # A visually different drone at the same location can still win a
    # motion-only active match, but its appearance must not rewrite ID 1.
    changed = _frame(color=(220, 80, 35))
    assert tracker.update(changed, [[25, 70, 85, 130]], [0.9], 1 / 30) == [1]
    assert len(tracker.tracks[1].gallery) == 1

    returned = tracker.update(first, [[25, 70, 85, 130]], [0.9], 2 / 30)
    assert returned == [1]


def test_unmatched_low_confidence_box_does_not_create_a_permanent_id() -> None:
    tracker = IdentityTracker(min_new_track_confidence=0.25)
    frame = _frame()

    assert tracker.update(frame, [[25, 70, 85, 130]], [0.18], 0.0) == [None]
    assert tracker.next_id == 1

    # If the same target becomes clear, its first confirmed ID starts at 1.
    assert tracker.update(frame, [[25, 70, 85, 130]], [0.8], 1 / 30) == [1]


def test_color_fingerprint_ignores_bright_wall_and_separates_drone_colors() -> None:
    red_on_white = np.full((32, 32, 3), 255, dtype=np.uint8)
    red_on_gray = np.full((32, 32, 3), 220, dtype=np.uint8)
    blue_on_white = np.full((32, 32, 3), 255, dtype=np.uint8)
    red_on_white[8:24, 8:24] = (0, 0, 210)
    red_on_gray[8:24, 8:24] = (0, 0, 210)
    blue_on_white[8:24, 8:24] = (210, 0, 0)

    red_white, _ = _descriptor(red_on_white)
    red_gray, _ = _descriptor(red_on_gray)
    blue_white, _ = _descriptor(blue_on_white)

    assert red_white is not None and red_gray is not None and blue_white is not None
    wall_shift = _appearance_distance([red_white], red_gray)
    color_shift = _appearance_distance([red_white], blue_white)
    assert wall_shift < 0.35
    assert color_shift > wall_shift


def test_multi_drone_crossing_keeps_ids_when_detection_order_changes() -> None:
    tracker = IdentityTracker()
    image, boxes = _two_drone_frame({1: 25, 2: 245})
    first = tracker.update(image, [boxes[1], boxes[2]], [0.9, 0.9], 0.0)
    assert first == [1, 2]

    # Detections return in reverse order as the two different drones move
    # toward and then across the frame. A per-edge greedy assignment used to
    # swap identities or allocate a new ID here.
    image, boxes = _two_drone_frame({1: 95, 2: 175})
    second = tracker.update(image, [boxes[2], boxes[1]], [0.9, 0.9], 1 / 30)
    assert second == [2, 1]

    image, boxes = _two_drone_frame({1: 165, 2: 105})
    third = tracker.update(image, [boxes[1], boxes[2]], [0.9, 0.9], 2 / 30)
    assert third == [1, 2]


def test_trackers_are_independent_between_video_streams() -> None:
    first_stream = IdentityTracker()
    second_stream = IdentityTracker()
    frame = _frame()

    assert first_stream.update(frame, [[25, 70, 85, 130]], [0.9], 0.0) == [1]
    assert second_stream.update(frame, [[25, 70, 85, 130]], [0.9], 0.0) == [1]
    first_stream.update(frame, [], [], 0.1)
    assert second_stream.update(frame, [[26, 70, 86, 130]], [0.9], 0.1) == [1]


def test_env_factory_defaults_and_overrides(monkeypatch) -> None:
    for name in (
        "ANTI_DRONE_ACTIVE_TRACK_TTL", "ANTI_DRONE_TRACK_TTL", "ANTI_DRONE_REID_MEMORY_SECONDS",
        "ANTI_DRONE_REID_MATCH_THRESHOLD", "ANTI_DRONE_NEW_TRACK_MIN_CONFIDENCE",
        "ANTI_DRONE_GALLERY_UPDATE_THRESHOLD",
    ):
        monkeypatch.delenv(name, raising=False)
    tracker = _TRACKER_MODULE.create_tracker_from_env()
    assert tracker.max_lost_seconds == 4.0
    assert tracker.reid_memory_seconds == 60.0
    assert tracker.reid_match_threshold == 0.45
    assert tracker.min_new_track_confidence == 0.25
    assert tracker.gallery_update_threshold == 0.15

    monkeypatch.setenv("ANTI_DRONE_TRACK_TTL", "2.5")
    monkeypatch.setenv("ANTI_DRONE_REID_MEMORY_SECONDS", "12")
    tracker = _TRACKER_MODULE.create_tracker_from_env()
    assert tracker.max_lost_seconds == 2.5
    assert tracker.reid_memory_seconds == 12.0
