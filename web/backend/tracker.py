"""Stateful multi-object tracker for the web runtime.

The web application receives frames from different transports (uploaded video
and the server camera).  Keeping identity association here means both paths
use the same ID/re-identification rules instead of displaying detection index
numbers that change every frame.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable

import cv2
import numpy as np


def _valid_box(box: Iterable[float]) -> bool:
    values = np.asarray(box, dtype=np.float32)
    return bool(
        values.shape == (4,)
        and np.isfinite(values).all()
        and values[2] > values[0]
        and values[3] > values[1]
    )


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    if not _valid_box(first) or not _valid_box(second):
        return 0.0
    x1 = max(float(first[0]), float(second[0]))
    y1 = max(float(first[1]), float(second[1]))
    x2 = min(float(first[2]), float(second[2]))
    y2 = min(float(first[3]), float(second[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, float(first[2] - first[0])) * max(0.0, float(first[3] - first[1]))
    area_b = max(0.0, float(second[2] - second[0])) * max(0.0, float(second[3] - second[1]))
    union = area_a + area_b - intersection
    return intersection / union if union > 1e-6 else 0.0


def _center_distance(first: np.ndarray, second: np.ndarray) -> float:
    first_center = np.array([(first[0] + first[2]) / 2.0, (first[1] + first[3]) / 2.0])
    second_center = np.array([(second[0] + second[2]) / 2.0, (second[1] + second[3]) / 2.0])
    diagonal_a = float(np.hypot(first[2] - first[0], first[3] - first[1]))
    diagonal_b = float(np.hypot(second[2] - second[0], second[3] - second[1]))
    diagonal = max(8.0, (diagonal_a + diagonal_b) / 2.0)
    return float(np.linalg.norm(first_center - second_center) / diagonal)


def _descriptor(crop: np.ndarray) -> tuple[np.ndarray | None, float]:
    """Create a cheap, lighting-tolerant visual fingerprint for a crop."""

    if crop is None or crop.ndim != 3 or crop.shape[0] < 4 or crop.shape[1] < 4:
        return None, 0.0
    resized = cv2.resize(np.ascontiguousarray(crop), (16, 16), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    gray = (gray - float(gray.mean())) / max(float(gray.std()), 1e-3)
    gray = np.clip(gray, -3.0, 3.0).reshape(-1)
    gray_norm = max(float(np.linalg.norm(gray)), 1e-6)
    gray /= gray_norm
    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    # Indoor clips often put a tiny drone against a large white wall. Hue is
    # undefined for that unsaturated background, so count hue only where there
    # is real chroma; saturation/value summaries still describe the full crop.
    chroma_mask = (
        (hsv[:, :, 1] >= 60) & (hsv[:, :, 2] >= 32)
    ).astype(np.uint8) * 255
    hue = cv2.calcHist([hsv], [0], chroma_mask, [16], [0, 180]).reshape(-1).astype(np.float32)
    saturation = cv2.calcHist([hsv], [1], None, [8], [0, 256]).reshape(-1).astype(np.float32)
    value = cv2.calcHist([hsv], [2], None, [8], [0, 256]).reshape(-1).astype(np.float32)
    # Normalize hue independently of the number of chromatic pixels. Otherwise
    # the white/gray background dilutes the hue cue until red and blue crops
    # become nearly indistinguishable.
    for histogram in (hue, saturation, value):
        histogram /= max(float(np.linalg.norm(histogram)), 1e-6)
    hist = np.concatenate((0.80 * hue, 0.10 * saturation, 0.10 * value)).astype(np.float32)
    hist /= max(float(np.linalg.norm(hist)), 1e-6)
    edges = cv2.Sobel(gray.reshape(16, 16), cv2.CV_32F, 1, 1, ksize=3).reshape(-1)
    edges /= max(float(np.linalg.norm(edges)), 1e-6)
    # Normalize each modality before mixing them. Previously the flattened
    # grayscale/edge pixels dominated the 28-bin HSV histogram by ~100:1, so
    # re-identification was mostly shape noise and ignored drone color.
    vector = np.concatenate((0.72 * hist, 0.18 * gray, 0.10 * edges)).astype(np.float32)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 1e-8:
        return None, 0.0
    vector /= norm
    quality = min(1.0, min(crop.shape[:2]) / 18.0) * min(1.0, crop.shape[0] * crop.shape[1] / 256.0)
    return vector, float(quality)


def _crop_descriptor(frame: np.ndarray, box: np.ndarray) -> tuple[np.ndarray | None, float]:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = map(float, box)
    # Use the detector's object crop without room/wall padding. A large margin
    # made indoor background pixels dominate the color histogram for tiny FPV.
    margin_x = (x2 - x1) * 0.02
    margin_y = (y2 - y1) * 0.02
    left = max(0, int(np.floor(x1 - margin_x)))
    top = max(0, int(np.floor(y1 - margin_y)))
    right = min(width, int(np.ceil(x2 + margin_x)))
    bottom = min(height, int(np.ceil(y2 + margin_y)))
    return _descriptor(frame[top:bottom, left:right])


def _appearance_distance(gallery: list[np.ndarray], descriptor: np.ndarray | None) -> float:
    if descriptor is None or not gallery:
        return float("inf")
    distances = []
    for reference in gallery:
        denominator = float(np.linalg.norm(reference) * np.linalg.norm(descriptor))
        if denominator > 1e-8:
            distances.append(float(np.clip(1.0 - np.dot(reference, descriptor) / denominator, 0.0, 2.0)))
    return min(distances, default=float("inf"))


def _minimum_cost_assignment(costs: list[list[float]]) -> list[tuple[int, int]]:
    """Rectangular Hungarian assignment, implemented without optional deps."""

    if not costs or not costs[0]:
        return []
    rows, columns = len(costs), len(costs[0])
    transposed = rows > columns
    matrix = [list(row) for row in costs]
    if transposed:
        matrix = [list(row) for row in zip(*matrix)]
        rows, columns = columns, rows

    # This potential-based Hungarian implementation requires rows <= columns.
    u = [0.0] * (rows + 1)
    v = [0.0] * (columns + 1)
    matched_row = [0] * (columns + 1)
    predecessor = [0] * (columns + 1)
    for row in range(1, rows + 1):
        matched_row[0] = row
        column0 = 0
        min_value = [float("inf")] * (columns + 1)
        used = [False] * (columns + 1)
        while True:
            used[column0] = True
            row0 = matched_row[column0]
            delta = float("inf")
            column1 = 0
            for column in range(1, columns + 1):
                if used[column]:
                    continue
                current = matrix[row0 - 1][column - 1] - u[row0] - v[column]
                if current < min_value[column]:
                    min_value[column] = current
                    predecessor[column] = column0
                if min_value[column] < delta:
                    delta = min_value[column]
                    column1 = column
            for column in range(columns + 1):
                if used[column]:
                    u[matched_row[column]] += delta
                    v[column] -= delta
                else:
                    min_value[column] -= delta
            column0 = column1
            if matched_row[column0] == 0:
                break
        while True:
            column1 = predecessor[column0]
            matched_row[column0] = matched_row[column1]
            column0 = column1
            if column0 == 0:
                break

    pairs = []
    for column in range(1, columns + 1):
        if matched_row[column] == 0:
            continue
        row_index, column_index = matched_row[column] - 1, column - 1
        pairs.append((column_index, row_index) if transposed else (row_index, column_index))
    return pairs


def _area(box: np.ndarray) -> float:
    return max(0.0, float(box[2] - box[0])) * max(0.0, float(box[3] - box[1]))


def _containment(first: np.ndarray, second: np.ndarray) -> float:
    """Share of the smaller box that lies inside the other one."""

    x1 = max(float(first[0]), float(second[0]))
    y1 = max(float(first[1]), float(second[1]))
    x2 = min(float(first[2]), float(second[2]))
    y2 = min(float(first[3]), float(second[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    smaller = min(_area(first), _area(second))
    return intersection / smaller if smaller > 1e-6 else 0.0


@dataclass
class _Track:
    # None while the track is tentative: it has not been seen often enough to
    # be shown or to consume a public ID.
    track_id: int | None
    box: np.ndarray
    previous_box: np.ndarray
    confidence: float
    last_seen: float
    # Last time a confident (not merely low-confidence) box supported it.
    last_strong_seen: float = 0.0
    missed_seconds: float = 0.0
    hits: int = 1
    gallery: list[np.ndarray] = field(default_factory=list, repr=False)
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(4, dtype=np.float32), repr=False)

    def predicted_box(self, elapsed: float) -> np.ndarray:
        return self.box + self.velocity * min(max(elapsed, 0.0), 1.0)


class IdentityTracker:
    """Motion + appearance association with short- and long-term ID memory.

    The detector is single-class, so the tracker is responsible for identity.
    Visible tracks are continued by motion only: a box must lie where the
    track could physically have moved to. A track that lost its object stays
    dormant and can be revived by appearance once a new object has been
    observed for confirm_hits frames. If the crop has no usable visual signal,
    a new ID is safer than silently assigning the wrong drone's ID.
    """

    def __init__(
        self,
        max_lost_seconds: float = 4.0,
        reid_memory_seconds: float = 60.0,
        reid_match_threshold: float = 0.45,
        reid_center_gate: float = 50.0,
        active_appearance_weight: float = 0.40,
        active_appearance_threshold: float = 0.65,
        min_new_track_confidence: float = 0.25,
        gallery_update_threshold: float = 0.15,
        confirm_hits: int = 1,
        motion_gate: float = 1.5,
        motion_gate_growth: float = 5.0,
        motion_gate_max: float = 8.0,
    ) -> None:
        self.max_lost_seconds = max(1.0, float(max_lost_seconds))
        self.reid_memory_seconds = max(self.max_lost_seconds, float(reid_memory_seconds))
        self.reid_match_threshold = max(0.05, min(1.0, float(reid_match_threshold)))
        self.reid_center_gate = max(4.0, float(reid_center_gate))
        self.active_appearance_weight = max(0.0, min(0.9, float(active_appearance_weight)))
        self.active_appearance_threshold = max(0.05, min(2.0, float(active_appearance_threshold)))
        self.min_new_track_confidence = max(0.0, min(1.0, float(min_new_track_confidence)))
        self.gallery_update_threshold = max(0.05, min(1.0, float(gallery_update_threshold)))
        # A box must persist this many frames before it gets an ID, so
        # one-frame false positives never become (or steal) an identity.
        self.confirm_hits = max(1, int(confirm_hits))
        # Search radius around the predicted position, in box diagonals: the
        # base value for a track seen on the previous frame, widened per
        # second without a detection. Measured FPV motion is ~0.2 diagonals
        # per frame at 30 fps, i.e. about 5 per second.
        self.motion_gate = max(0.25, float(motion_gate))
        self.motion_gate_growth = max(0.0, float(motion_gate_growth))
        self.motion_gate_max = max(self.motion_gate, float(motion_gate_max))
        self.tentative_ttl = 0.5
        self.weak_min_iou = 0.10
        self.weak_bridge_seconds = 1.0
        self._now = 0.0
        self.reid_min_gap = 0.25
        self.duplicate_containment = 0.7
        self.next_id = 1
        self.tracks: dict[int, _Track] = {}
        self.tentative: list[_Track] = []
        self.last_timestamp: float | None = None

    def reset(self) -> None:
        self.next_id = 1
        self.tracks.clear()
        self.tentative.clear()
        self.last_timestamp = None

    def _make_detections(self, frame: np.ndarray, boxes: list[list[float]], confidences: list[float]):
        candidates = []
        for index, box in enumerate(boxes):
            array = np.asarray(box, dtype=np.float32)
            if not _valid_box(array):
                continue
            candidates.append((float(confidences[index]), index, array))
        # The detector sometimes returns a second box nested in (or wrapped
        # around) the same drone, which NMS keeps because the IoU is low.
        candidates.sort(key=lambda item: -item[0])
        detections = []
        for confidence, index, array in candidates:
            if any(
                _containment(array, kept["box"]) >= self.duplicate_containment
                for kept in detections
            ):
                continue
            descriptor, quality = _crop_descriptor(frame, array)
            detections.append({
                "source_index": index,
                "box": array,
                "confidence": confidence,
                "descriptor": descriptor,
                "quality": quality,
            })
        detections.sort(key=lambda item: item["source_index"])
        return detections

    def _update_gallery(self, track: _Track, detection: dict) -> None:
        descriptor = detection["descriptor"]
        if (
            descriptor is None
            or detection["quality"] < 0.35
            or detection["confidence"] < self.min_new_track_confidence
        ):
            return
        # Keep the gallery anchored to confirmed appearance. A bad active
        # association must not teach the old identity how another drone looks.
        if track.gallery and _appearance_distance(track.gallery, descriptor) > self.gallery_update_threshold:
            return
        track.gallery.append(descriptor)
        track.gallery = track.gallery[-12:]

    def _motion_cost(self, track: _Track, detection: dict, weak: bool = False) -> float | None:
        """Association cost, or None when the box is not reachable by this track."""

        predicted = track.predicted_box(track.missed_seconds)
        box = detection["box"]
        iou = _iou(predicted, box)
        center = _center_distance(predicted, box)
        gate = min(self.motion_gate_max, self.motion_gate + self.motion_gate_growth * track.missed_seconds)
        if weak:
            # A low-confidence box is only trusted right where the track is,
            # and only to bridge a short dropout. Static clutter scores low
            # but steadily; without the time limit a track that passes it
            # would settle on it for good.
            if iou < self.weak_min_iou:
                return None
            if self._now - track.last_strong_seen > self.weak_bridge_seconds:
                return None
        elif iou < 0.01 and center > gate:
            return None
        appearance = _appearance_distance(track.gallery, detection["descriptor"])
        usable_appearance = bool(np.isfinite(appearance) and detection["quality"] >= 0.20)
        if usable_appearance and appearance > self.active_appearance_threshold and iou < 0.05:
            # Do not swap two non-overlapping drones just because the motion
            # gate made their boxes assignable.
            return None
        if usable_appearance:
            app_cost = min(appearance / 0.80, 1.0)
            appearance_weight = self.active_appearance_weight
            motion_weight = 1.0 - appearance_weight
            return (
                motion_weight * 0.625 * (1.0 - iou)
                + motion_weight * 0.375 * min(center / gate, 1.0)
                + appearance_weight * app_cost
            )
        return 0.60 * (1.0 - iou) + 0.40 * min(center / gate, 1.0)

    def _associate(
        self,
        tracks: list[_Track],
        detections: list[dict],
        detection_indices: list[int],
        weak: bool = False,
    ) -> list[tuple[_Track, int]]:
        """Global one-to-one motion assignment between tracks and detections."""

        if not tracks or not detection_indices:
            return []
        invalid_cost = 1_000_000.0
        costs = []
        for track in tracks:
            row = []
            for detection_index in detection_indices:
                cost = self._motion_cost(track, detections[detection_index], weak)
                row.append(invalid_cost if cost is None or cost > 0.92 else cost)
            costs.append(row)
        pairs = []
        for row_index, column in _minimum_cost_assignment(costs):
            if costs[row_index][column] >= invalid_cost:
                continue
            pairs.append((tracks[row_index], detection_indices[column]))
        return pairs

    def _observe(self, track: _Track, detection: dict, timestamp: float, revived: bool = False) -> None:
        old_box = track.box.copy()
        track.previous_box = old_box
        track.box = detection["box"].copy()
        if revived:
            # Stale velocity is not a useful predictor after a re-entry.
            track.velocity = np.zeros(4, dtype=np.float32)
        else:
            # Divide by the time since this track was last seen, not by the
            # frame interval: after a short dropout the latter overstates the
            # speed many times and throws the next prediction off the object.
            measured_velocity = (track.box - old_box) / max(track.missed_seconds, 1e-3)
            # Smooth detector jitter without discarding real fast motion.
            track.velocity = 0.25 * track.velocity + 0.75 * measured_velocity
        track.confidence = detection["confidence"]
        track.last_seen = timestamp
        if detection["confidence"] >= self.min_new_track_confidence:
            track.last_strong_seen = timestamp
        track.missed_seconds = 0.0
        track.hits += 1
        self._update_gallery(track, detection)

    def update(
        self,
        frame: np.ndarray,
        boxes: list[list[float]],
        confidences: list[float],
        timestamp: float,
    ) -> list[int | None]:
        timestamp = float(timestamp)
        if self.last_timestamp is None:
            elapsed = 1.0 / 15.0
        else:
            # Keep real source-time gaps for dormant-track expiry and re-ID.
            # Motion prediction itself is clamped in _Track.predicted_box().
            elapsed = max(1e-3, timestamp - self.last_timestamp)
        self.last_timestamp = timestamp
        self._now = timestamp

        detections = self._make_detections(frame, boxes, confidences)
        for track in self.tracks.values():
            track.missed_seconds += elapsed
        for track in self.tentative:
            track.missed_seconds += elapsed

        matched_tracks: set[int] = set()
        matched_detections: set[int] = set()
        assigned: list[int | None] = [None] * len(boxes)
        strong = [
            index for index, detection in enumerate(detections)
            if detection["confidence"] >= self.min_new_track_confidence
        ]
        weak = [index for index in range(len(detections)) if index not in strong]

        # 1. Continue visible tracks with confident boxes, then let the
        #    leftover low-confidence boxes bridge tracks the detector almost
        #    lost. Both passes are motion-gated: a track never takes a box it
        #    could not have reached.
        for candidates, is_weak in ((strong, False), (weak, True)):
            visible = [
                track for track_id, track in self.tracks.items()
                if track_id not in matched_tracks and track.missed_seconds <= self.max_lost_seconds
            ]
            for track, detection_index in self._associate(visible, detections, candidates, is_weak):
                detection = detections[detection_index]
                self._observe(track, detection, timestamp)
                assigned[detection["source_index"]] = track.track_id
                matched_tracks.add(track.track_id)
                matched_detections.add(detection_index)

        # 2. Confident boxes that no visible track explains are new objects.
        #    They stay tentative until seen confirm_hits times.
        remaining = [index for index in strong if index not in matched_detections]
        confirming: list[tuple[_Track, int]] = []
        for track, detection_index in self._associate(self.tentative, detections, remaining):
            self._observe(track, detections[detection_index], timestamp)
            matched_detections.add(detection_index)
            if track.hits >= self.confirm_hits:
                confirming.append((track, detection_index))
        for detection_index in remaining:
            if detection_index in matched_detections:
                continue
            detection = detections[detection_index]
            track = _Track(
                track_id=None,
                box=detection["box"].copy(),
                previous_box=detection["box"].copy(),
                confidence=detection["confidence"],
                last_seen=timestamp,
                last_strong_seen=timestamp,
            )
            if detection["descriptor"] is not None and detection["quality"] >= 0.25:
                track.gallery.append(detection["descriptor"])
            if self.confirm_hits <= 1:
                confirming.append((track, detection_index))
            else:
                self.tentative.append(track)
        confirming.sort(key=lambda item: detections[item[1]]["source_index"])

        # 3. A newly confirmed object is first compared with the tracks that
        #    lost their drone: a returning drone gets its old ID back when its
        #    appearance clearly matches exactly one of them.
        invalid_cost = 1_000_000.0
        lost_tracks = [
            track for track_id, track in self.tracks.items()
            if track_id not in matched_tracks
            and self.reid_min_gap <= track.missed_seconds <= self.reid_memory_seconds
        ]
        reid_costs: list[list[float]] = []
        for track in lost_tracks:
            predicted = track.predicted_box(track.missed_seconds)
            row = []
            for _, detection_index in confirming:
                detection = detections[detection_index]
                appearance = _appearance_distance(track.gallery, detection["descriptor"])
                if (
                    not np.isfinite(appearance)
                    or appearance > self.reid_match_threshold
                    or detection["quality"] < 0.20
                ):
                    row.append(invalid_cost)
                    continue
                # A returning FPV may re-enter far from its last visible
                # position, and stale velocity is not a useful predictor after
                # several seconds without observations. Use location to rank
                # otherwise-similar identities, not as a hard re-ID veto.
                center = _center_distance(predicted, detection["box"])
                row.append(0.85 * appearance + 0.15 * min(center / self.reid_center_gate, 1.0))
            reid_costs.append(row)

        revived: dict[int, _Track] = {}
        if lost_tracks and confirming:
            for track_row, column in _minimum_cost_assignment(reid_costs):
                if reid_costs[track_row][column] >= invalid_cost:
                    continue
                candidate_scores = sorted(
                    reid_costs[row_index][column]
                    for row_index in range(len(lost_tracks))
                    if reid_costs[row_index][column] < invalid_cost
                )
                if len(candidate_scores) > 1 and candidate_scores[1] - candidate_scores[0] < 0.06:
                    continue
                revived[column] = lost_tracks[track_row]

        for column, (candidate, detection_index) in enumerate(confirming):
            detection = detections[detection_index]
            if column in revived:
                track = revived[column]
                self._observe(track, detection, timestamp, revived=True)
            else:
                track = candidate
                track.track_id = self.next_id
                self.next_id += 1
                self.tracks[track.track_id] = track
            assigned[detection["source_index"]] = track.track_id
        confirmed = {id(candidate) for candidate, _ in confirming}
        self.tentative = [
            track for track in self.tentative
            if id(track) not in confirmed and track.missed_seconds <= self.tentative_ttl
        ]

        expired = [
            track_id
            for track_id, track in self.tracks.items()
            if track.missed_seconds > self.reid_memory_seconds
        ]
        for track_id in expired:
            del self.tracks[track_id]
        return assigned

    def active_ids(self) -> list[int]:
        return sorted(track_id for track_id, track in self.tracks.items() if track.missed_seconds <= 0.2)


def create_tracker_from_env(confirm_hits: int | None = None) -> IdentityTracker:
    """Build a tracker from ANTI_DRONE_* settings; the single source of defaults.

    Streams wait ANTI_DRONE_TRACK_CONFIRM_HITS frames before showing a new
    object. Pass confirm_hits=1 for a single still image.
    """

    active_ttl = os.getenv("ANTI_DRONE_ACTIVE_TRACK_TTL", os.getenv("ANTI_DRONE_TRACK_TTL", "4.0"))
    return IdentityTracker(
        max_lost_seconds=float(active_ttl),
        reid_memory_seconds=float(os.getenv("ANTI_DRONE_REID_MEMORY_SECONDS", "60.0")),
        reid_match_threshold=float(os.getenv("ANTI_DRONE_REID_MATCH_THRESHOLD", "0.45")),
        min_new_track_confidence=float(os.getenv("ANTI_DRONE_NEW_TRACK_MIN_CONFIDENCE", "0.25")),
        gallery_update_threshold=float(os.getenv("ANTI_DRONE_GALLERY_UPDATE_THRESHOLD", "0.15")),
        confirm_hits=(
            int(os.getenv("ANTI_DRONE_TRACK_CONFIRM_HITS", "3")) if confirm_hits is None else confirm_hits
        ),
        motion_gate=float(os.getenv("ANTI_DRONE_MOTION_GATE", "1.5")),
        motion_gate_growth=float(os.getenv("ANTI_DRONE_MOTION_GATE_GROWTH", "5.0")),
    )
