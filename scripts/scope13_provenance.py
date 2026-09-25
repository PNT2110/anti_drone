"""Pure helpers for conservative Scope 13 provenance decisions."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


RGBT_RE = re.compile(r"^RGBT_(train|val|test)_(\d{8})_(\d{6})_(\d+)_(\d+)_(visible|infrared)_(\d+)\.jpg$")


def parse_rgbt_basename(name: str) -> dict[str, Any] | None:
    match = RGBT_RE.match(name)
    if not match:
        return None
    source_split, date, clock, stream_id, sequence_id, modality, frame = match.groups()
    return {
        "source_split": source_split,
        "date": date,
        "clock": clock,
        "stream_id": stream_id,
        "sequence_id": sequence_id,
        "modality": modality,
        "source_frame_index": int(frame),
        "archive_sequence_id": f"{date}_{clock}_{stream_id}_{sequence_id}",
        "session_prefix": f"RGBT_{source_split}_{date}_{clock}",
        "group": f"base:RGBT_{source_split}_{date}_{clock}_{stream_id}_{sequence_id}",
    }


def classify_prefix(*, archive_sequence_ids: set[str], explicit_session_ids: set[str] | None = None) -> tuple[str, str]:
    """Return source-directory status and separate session-level status.

    Distinct archive sequence directories are evidence of distinct source
    sequences.  Without an explicit session identifier, they cannot prove
    that the recordings were independent sessions.
    """

    if not archive_sequence_ids:
        return "UNRESOLVED", "UNRESOLVED"
    if explicit_session_ids and len(explicit_session_ids) == 1:
        return "CONFIRMED_SHARED_SESSION", "CONFIRMED_SHARED_SESSION"
    return "CONFIRMED_DISTINCT_SOURCES", "UNRESOLVED"


def confirmed_cross_split_collisions(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    splits_by_source: dict[str, set[str]] = defaultdict(set)
    groups_by_source: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.get("mapping_status") == "CONFIRMED":
            source = record.get(key)
            if source:
                splits_by_source[source].add(record["split"])
                groups_by_source[source].add(record["group"])
    return [
        {"source_key": source, "splits": sorted(splits_by_source[source]), "groups": sorted(groups_by_source[source])}
        for source in sorted(splits_by_source)
        if len(splits_by_source[source]) > 1
    ]
