"""Shared detection and track data structures.

The types deliberately contain no inference-backend code so that the tracker
can be replayed from stored detections on a Raspberry Pi or a development
host.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class TrackState(str, Enum):
    TENTATIVE = "TENTATIVE"
    CONFIRMED = "CONFIRMED"
    LOST = "LOST"
    REMOVED = "REMOVED"


@dataclass
class Detection:
    box: np.ndarray
    confidence: float
    class_id: int = 0


@dataclass
class Track:
    track_id: int
    bbox_observed: np.ndarray | None
    bbox_predicted: np.ndarray
    confidence: float
    state: TrackState = TrackState.TENTATIVE
    matched_this_frame: bool = False
    last_observed_at: float | None = None
    observation_count: int = 0
    high_confidence_observations: int = 0
    missed_seconds: float = 0.0
    hits: int = 0
    missed: int = 0
    last_frame: int = 0
    last_source_frame: int | None = None
    _seen_source_frames: set[int] = field(default_factory=set, repr=False)

    @property
    def box(self) -> np.ndarray:
        """Backward-compatible display box: observation, otherwise prediction."""

        return self.bbox_observed if self.matched_this_frame and self.bbox_observed is not None else self.bbox_predicted

    @property
    def bbox(self) -> np.ndarray:
        return self.box

    @property
    def is_observed(self) -> bool:
        return self.matched_this_frame and self.bbox_observed is not None

    def mark_source_frame(self, source_frame_id: int | None) -> bool:
        """Return whether this source frame is new for this track."""

        if source_frame_id is None:
            return True
        if source_frame_id in self._seen_source_frames:
            return False
        self._seen_source_frames.add(source_frame_id)
        if len(self._seen_source_frames) > 128:
            self._seen_source_frames = set(sorted(self._seen_source_frames)[-64:])
        self.last_source_frame = source_frame_id
        return True
