"""The original bounded greedy tracker preserved for ablation and rollback."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .association import box_iou
from .types import Detection, Track, TrackState


class ByteTrackLegacy:
    """Compatibility implementation of the pre-motion ByteTrackLite behavior."""

    def __init__(self, high_threshold: float = 0.25, low_threshold: float = 0.10, match_iou: float = 0.30, max_lost: int = 15):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.match_iou = match_iou
        self.max_lost = max_lost
        self.next_id = 1
        self.tracks: dict[int, Track] = {}

    def reset(self) -> None:
        self.next_id = 1
        self.tracks.clear()

    def update(self, detections: list[Detection], frame_id: int = 0, timestamp: float | None = None, source_frame_id: int | None = None) -> list[Track]:
        # Keep the original ``update(detections, frame_id)`` positional API.
        timestamp = float(frame_id if timestamp is None else timestamp)
        candidates = [d for d in detections if d.confidence >= self.low_threshold]
        unmatched = set(range(len(candidates)))
        for track in list(self.tracks.values()):
            track.matched_this_frame = False
            best_index, best_iou = -1, 0.0
            for index in unmatched:
                overlap = box_iou(track.box, candidates[index].box)
                if overlap > best_iou:
                    best_index, best_iou = index, overlap
            if best_index >= 0 and best_iou >= self.match_iou:
                if source_frame_id is not None and source_frame_id in track._seen_source_frames:
                    # A replayed source frame is not a new observation and
                    # must not become a second track after this match.
                    unmatched.remove(best_index)
                    track.matched_this_frame = False
                    track.last_frame = frame_id
                    continue
                detection = candidates[best_index]
                track.bbox_observed = detection.box.astype(np.float32, copy=True)
                track.bbox_predicted = track.bbox_observed.copy()
                track.confidence = float(detection.confidence)
                track.matched_this_frame = True
                track.last_observed_at = timestamp
                track.observation_count += 1
                track.high_confidence_observations += int(detection.confidence >= self.high_threshold)
                track.hits += 1
                track.missed = 0
                track.missed_seconds = 0.0
                track.last_frame = frame_id
                track.state = TrackState.CONFIRMED if track.observation_count >= 2 else TrackState.TENTATIVE
                track.mark_source_frame(source_frame_id)
                unmatched.remove(best_index)
            else:
                track.missed += 1
                track.last_frame = frame_id
                track.missed_seconds = track.missed + 0.0
                track.state = TrackState.LOST
        for index in unmatched:
            detection = candidates[index]
            if detection.confidence >= self.high_threshold:
                box = detection.box.astype(np.float32, copy=True)
                self.tracks[self.next_id] = Track(
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
                self.tracks[self.next_id].mark_source_frame(source_frame_id)
                self.next_id += 1
        self.tracks = {key: value for key, value in self.tracks.items() if value.missed <= self.max_lost}
        return list(self.tracks.values())


ByteTrackLite = ByteTrackLegacy
