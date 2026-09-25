"""Small, conservative provenance classification helpers for Scope 11."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


STATUSES = {
    "CONFIRMED_SOURCE_SEQUENCE",
    "CONFIRMED_INDEPENDENT_IMAGE",
    "POSSIBLE_MATCH",
    "UNRESOLVED",
}


def classify_match(*, exact_archive_member: bool, exact_tracking_members: list[str], independent_metadata: bool = False) -> str:
    """Never promote a basename or ambiguous exact match to a stronger class."""

    if independent_metadata:
        return "CONFIRMED_INDEPENDENT_IMAGE"
    if len(exact_tracking_members) == 1:
        return "CONFIRMED_SOURCE_SEQUENCE"
    if len(exact_tracking_members) > 1:
        return "POSSIBLE_MATCH"
    if exact_archive_member:
        return "UNRESOLVED"
    return "UNRESOLVED"


def group_aliases(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, set[str]] = defaultdict(set)
    for record in records:
        source_key = record.get("source_sequence_key")
        if source_key and record.get("provenance_status") == "CONFIRMED_SOURCE_SEQUENCE":
            by_source[source_key].add(record.get("v2_group", ""))
    aliases = []
    for source_key, groups in sorted(by_source.items()):
        groups.discard("")
        if len(groups) > 1:
            aliases.append({"collision_type": "SOURCE_GROUP_ALIAS", "source_sequence_key": source_key, "v2_groups": sorted(groups)})
    return aliases


def promote_possible(status: str) -> str:
    """Guard used by tests and callers: POSSIBLE_MATCH cannot become confirmed."""

    if status not in STATUSES:
        raise ValueError(status)
    return status
