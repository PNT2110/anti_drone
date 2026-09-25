"""Two-stage ByteTrack with timestamp-aware Kalman prediction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .association import assign_min_cost, box_iou, normalized_center_distance, valid_box
from .kalman import KalmanBoxFilter
from .lifecycle import LifecycleConfig, mark_matched, mark_unmatched
from .types import Detection, Track, TrackState


@dataclass(frozen=True)
class ByteTrackConfig:
    detector_confidence_floor: float = 0.10
    track_low_thresh: float = 0.10
    track_high_thresh: float = 0.25
    new_track_thresh: float = 0.35
    match_iou: float = 0.30
    adaptive_center_gate: float = 2.50
    adaptive_mahalanobis_gate: float = 25.0
    process_noise: float = 1.0
    measurement_noise: float = 4.0
    min_confirmed_observations: int = 2
    max_lost_seconds: float = 0.60
    max_gap_before_reset_seconds: float = 1.00

    def validate(self) -> None:
        values = (self.detector_confidence_floor, self.track_low_thresh, self.track_high_thresh, self.new_track_thresh)
        if any(not np.isfinite(value) or not 0 <= value <= 1 for value in values):
            raise ValueError("detector and tracker confidence thresholds must be finite values in [0, 1]")
        if self.detector_confidence_floor > self.track_low_thresh:
            raise ValueError("detector_confidence_floor must be <= track_low_thresh")
        if not self.track_low_thresh < self.track_high_thresh <= self.new_track_thresh <= 1:
            raise ValueError("thresholds must satisfy low < high <= new_track <= 1")
        if self.max_lost_seconds <= 0 or self.max_gap_before_reset_seconds <= 0:
            raise ValueError("track timeout values must be positive")


class ByteTrack:
    """ByteTrack high/low association with configurable motion gating."""

    def __init__(self, config: ByteTrackConfig | None = None, mode: str = "motion_adaptive"):
        self.config = config or ByteTrackConfig()
        self.config.validate()
        if mode not in {"motion", "motion_adaptive"}:
            raise ValueError(f"unsupported motion tracker mode: {mode}")
        self.mode = mode
        self.lifecycle = LifecycleConfig(
            min_confirmed_observations=self.config.min_confirmed_observations,
            max_lost_seconds=self.config.max_lost_seconds,
            max_gap_before_reset_seconds=self.config.max_gap_before_reset_seconds,
        )
        self.next_id = 1
        self.tracks: dict[int, Track] = {}
        self.filters: dict[int, KalmanBoxFilter] = {}
        self._last_timestamp: float | None = None

    def reset(self) -> None:
        self.next_id = 1
        self.tracks.clear()
        self.filters.clear()
        self._last_timestamp = None

    def _validate_timestamp(self, timestamp: float) -> float:
        value = float(timestamp)
        if not np.isfinite(value):
            raise ValueError(f"timestamp must be finite, got {timestamp!r}")
        if self._last_timestamp is not None and value < self._last_timestamp:
            raise ValueError(f"timestamp moved backwards: {value} < {self._last_timestamp}")
        self._last_timestamp = value
        return value

    def _predict(self, timestamp: float) -> None:
        for track_id, track in list(self.tracks.items()):
            kalman = self.filters[track_id]
            predicted, _, _ = kalman.predict(timestamp)
            track.bbox_predicted = predicted
            track.bbox_observed = None
            track.matched_this_frame = False

    def _cost(self, track: Track, detection: Detection, track_id: int) -> float:
        if not valid_box(detection.box) or not valid_box(track.bbox_predicted):
            return float("inf")
        iou = box_iou(track.bbox_predicted, detection.box)
        mahalanobis = self.filters[track_id].mahalanobis(detection.box)
        if self.mode == "motion":
            if iou < self.config.match_iou or mahalanobis > self.config.adaptive_mahalanobis_gate:
                return float("inf")
            return 1.0 - iou
        center = normalized_center_distance(track.bbox_predicted, detection.box)
        if mahalanobis > self.config.adaptive_mahalanobis_gate:
            return float("inf")
        if iou < self.config.match_iou and center > self.config.adaptive_center_gate:
            return float("inf")
        return 0.70 * (1.0 - iou) + 0.20 * min(center / self.config.adaptive_center_gate, 1.0) + 0.10 * min(mahalanobis / self.config.adaptive_mahalanobis_gate, 1.0)

    def _associate(self, track_ids: list[int], detections: list[Detection]) -> tuple[dict[int, int], set[int]]:
        if not track_ids or not detections:
            return {}, set()
        matrix = np.full((len(track_ids), len(detections)), np.inf, dtype=np.float64)
        for row, track_id in enumerate(track_ids):
            for col, detection in enumerate(detections):
                matrix[row, col] = self._cost(self.tracks[track_id], detection, track_id)
        pairs = assign_min_cost(matrix)
        matched_tracks: dict[int, int] = {}
        matched_detections: set[int] = set()
        for row, col in pairs:
            if np.isfinite(matrix[row, col]):
                matched_tracks[track_ids[row]] = col
                matched_detections.add(col)
        return matched_tracks, matched_detections

    def _apply_match(self, track_id: int, detection: Detection, timestamp: float, frame_id: int, source_frame_id: int | None) -> bool:
        track = self.tracks[track_id]
        self.filters[track_id].update(detection.box, timestamp)
        track.bbox_observed = detection.box.astype(np.float32, copy=True)
        track.bbox_predicted = track.bbox_observed.copy()
        track.confidence = float(detection.confidence)
        matched = mark_matched(track, timestamp, frame_id, detection.confidence >= self.config.track_high_thresh, source_frame_id, self.lifecycle)
        if not matched:
            track.bbox_observed = None
        return matched

    def update(self, detections: list[Detection], timestamp: float, frame_id: int = 0, source_frame_id: int | None = None) -> list[Track]:
        previous_timestamp = self._last_timestamp
        timestamp = self._validate_timestamp(timestamp)
        if previous_timestamp is not None and timestamp - previous_timestamp > self.config.max_gap_before_reset_seconds:
            # A reconnect or a long pause starts a fresh tracking session.  Do
            # not let stale motion state claim the first post-gap detection.
            self.tracks.clear()
            self.filters.clear()
            self.next_id = 1
        detections = [d for d in detections if valid_box(d.box) and np.isfinite(d.confidence) and d.confidence >= self.config.track_low_thresh]
        self._predict(timestamp)
        high = [d for d in detections if d.confidence >= self.config.track_high_thresh]
        low = [d for d in detections if self.config.track_low_thresh <= d.confidence < self.config.track_high_thresh]
        active_ids = [track_id for track_id, track in self.tracks.items() if track.state != TrackState.REMOVED]
        first_tracks, matched_high = self._associate(active_ids, high)
        matched_ids: set[int] = set()
        for track_id, detection_index in first_tracks.items():
            if self._apply_match(track_id, high[detection_index], timestamp, frame_id, source_frame_id):
                matched_ids.add(track_id)
        remaining_ids = [track_id for track_id in active_ids if track_id not in matched_ids]
        second_tracks, _ = self._associate(remaining_ids, low)
        for track_id, detection_index in second_tracks.items():
            if self._apply_match(track_id, low[detection_index], timestamp, frame_id, source_frame_id):
                matched_ids.add(track_id)
        for track_id in list(active_ids):
            if track_id not in matched_ids and track_id in self.tracks:
                if not mark_unmatched(self.tracks[track_id], timestamp, frame_id, self.lifecycle):
                    self.tracks.pop(track_id, None)
                    self.filters.pop(track_id, None)
        used_high = matched_high
        for index, detection in enumerate(high):
            if index in used_high or detection.confidence < self.config.new_track_thresh:
                continue
            box = detection.box.astype(np.float32, copy=True)
            track = Track(
                track_id=self.next_id,
                bbox_observed=box.copy(),
                bbox_predicted=box.copy(),
                confidence=float(detection.confidence),
                matched_this_frame=True,
                last_observed_at=timestamp,
                observation_count=1,
                high_confidence_observations=1,
                hits=1,
                last_frame=frame_id,
                last_source_frame=source_frame_id,
            )
            track.mark_source_frame(source_frame_id)
            self.tracks[self.next_id] = track
            self.filters[self.next_id] = KalmanBoxFilter(box, timestamp, self.config.process_noise, self.config.measurement_noise)
            self.next_id += 1
        return list(self.tracks.values())
