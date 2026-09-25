"""Alert confirmation based only on real matched observations."""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass

from anti_drone.tracking.types import Track


@dataclass(frozen=True)
class AlertEvent:
    event_id: str
    session_id: str
    track_id: int
    timestamp: float
    bbox: tuple[float, float, float, float]
    confidence: float
    observation_count: int


class TemporalAlert:
    def __init__(self, min_observations: int = 3, min_high_confidence_observations: int = 2, confirmation_window_seconds: float = 0.60, cooldown_seconds: float = 2.0, high_confidence_threshold: float = 0.25, session_id: str | None = None):
        if min_observations < 1 or min_high_confidence_observations < 0 or confirmation_window_seconds <= 0 or cooldown_seconds < 0 or not 0 <= high_confidence_threshold <= 1:
            raise ValueError("invalid temporal alert configuration")
        self.min_observations = min_observations
        self.min_high_confidence_observations = min_high_confidence_observations
        self.confirmation_window_seconds = confirmation_window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.high_confidence_threshold = high_confidence_threshold
        self.session_id = session_id or uuid.uuid4().hex
        self.history: dict[int, deque[tuple[float, float, bool, int | None]]] = defaultdict(deque)
        self.last_alert: dict[int, float] = {}
        self.seen_source_frames: dict[int, set[int]] = defaultdict(set)

    def reset(self, session_id: str | None = None) -> None:
        self.history.clear()
        self.last_alert.clear()
        self.seen_source_frames.clear()
        self.session_id = session_id or uuid.uuid4().hex

    def update(self, tracks: list[Track], timestamp: float) -> tuple[list[Track], list[AlertEvent]]:
        alerts: list[Track] = []
        events: list[AlertEvent] = []
        active_ids = {track.track_id for track in tracks}
        for track in tracks:
            source_frame = track.last_source_frame
            if not track.matched_this_frame or (source_frame is not None and source_frame in self.seen_source_frames[track.track_id]):
                continue
            if source_frame is not None:
                self.seen_source_frames[track.track_id].add(source_frame)
            history = self.history[track.track_id]
            history.append((timestamp, track.confidence, track.confidence >= self.high_confidence_threshold, track.last_source_frame))
            while history and timestamp - history[0][0] > self.confirmation_window_seconds:
                history.popleft()
            high_count = sum(item[2] for item in history)
            previous = self.last_alert.get(track.track_id)
            if len(history) < self.min_observations or high_count < self.min_high_confidence_observations:
                continue
            if previous is not None and timestamp - previous < self.cooldown_seconds:
                continue
            self.last_alert[track.track_id] = timestamp
            alerts.append(track)
            events.append(AlertEvent(uuid.uuid4().hex, self.session_id, track.track_id, timestamp, tuple(map(float, track.box)), track.confidence, len(history)))
        for track_id in set(self.history) - active_ids:
            self.history.pop(track_id, None)
            self.last_alert.pop(track_id, None)
            self.seen_source_frames.pop(track_id, None)
        return alerts, events
