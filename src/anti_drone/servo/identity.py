"""Stable public identity for the single-drone live tracking session."""

from __future__ import annotations


class SingleDroneSessionIdentity:
    """Expose one stable target ID while retaining ByteTrack diagnostics.

    ByteTrack IDs are short-lived motion-track identities, not physical ReID.
    The live anti-drone runtime currently selects one physical target, so its
    public session identity remains 1 across internal track loss/recreation.
    ``tracker_target_id`` remains available for auditing every reassociation.
    This class does not claim cross-session or multi-drone identity recognition.
    """

    def __init__(self, public_id: int = 1) -> None:
        if public_id < 1:
            raise ValueError("public_id must be positive")
        self.public_id = int(public_id)
        self.last_tracker_id: int | None = None
        self.tracker_id_changes = 0

    def apply(self, result: dict) -> dict:
        tracker_id = result.get("target_id")
        if tracker_id is not None:
            tracker_id = int(tracker_id)
            if self.last_tracker_id is not None and tracker_id != self.last_tracker_id:
                self.tracker_id_changes += 1
            self.last_tracker_id = tracker_id
        return {
            **result,
            "tracker_target_id": tracker_id,
            "target_id": self.public_id if tracker_id is not None else None,
            "identity_mode": "SINGLE_DRONE_SESSION",
            "tracker_id_changes": self.tracker_id_changes,
        }
