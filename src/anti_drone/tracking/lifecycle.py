"""Track lifecycle policy shared by motion trackers."""

from __future__ import annotations

from dataclasses import dataclass

from .types import Track, TrackState


@dataclass(frozen=True)
class LifecycleConfig:
    min_confirmed_observations: int = 2
    max_lost_seconds: float = 0.60
    max_gap_before_reset_seconds: float = 1.00


def mark_matched(track: Track, timestamp: float, frame_id: int, high_confidence: bool, source_frame_id: int | None, config: LifecycleConfig | None = None) -> bool:
    if source_frame_id is not None and source_frame_id in track._seen_source_frames:
        track.matched_this_frame = False
        return False
    track.matched_this_frame = True
    track.last_observed_at = float(timestamp)
    track.missed_seconds = 0.0
    track.missed = 0
    track.hits += 1
    track.last_frame = frame_id
    track.observation_count += 1
    if high_confidence:
        track.high_confidence_observations += 1
    track.mark_source_frame(source_frame_id)
    minimum = config.min_confirmed_observations if config is not None else 2
    if track.observation_count >= minimum:
        track.state = TrackState.CONFIRMED
    return True


def mark_unmatched(track: Track, timestamp: float, frame_id: int, config: LifecycleConfig) -> bool:
    track.matched_this_frame = False
    track.missed += 1
    track.last_frame = frame_id
    if track.last_observed_at is None:
        track.missed_seconds = float("inf")
    else:
        track.missed_seconds = max(0.0, float(timestamp) - track.last_observed_at)
    if track.missed_seconds > config.max_lost_seconds or track.missed_seconds > config.max_gap_before_reset_seconds:
        track.state = TrackState.REMOVED
        return False
    track.state = TrackState.LOST
    return True
