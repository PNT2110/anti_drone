"""Pure deterministic policies used by the Scope 14 dry run."""

from __future__ import annotations

import hashlib
from typing import Any


RATIOS = {"train": 0.70, "val": 0.20, "test": 0.10}


def strict_original_split_assignment(original_source_split: str) -> str:
    if original_source_split not in RATIOS:
        raise ValueError(original_source_split)
    return original_source_split


def holdout_conflict(original_source_split: str, proposed_split: str) -> bool:
    """A strict policy keeps official source partitions on their same side."""

    return strict_original_split_assignment(original_source_split) != proposed_split


def deterministic_prefix_target_assignment(groups: list[dict[str, Any]], seed: int = 42) -> dict[str, str]:
    """Assign whole prefix groups toward 70/20/10 without seed searching."""

    total = sum(int(group["sample_count"]) for group in groups)
    targets = {split: total * ratio for split, ratio in RATIOS.items()}
    ordered = sorted(
        groups,
        key=lambda group: (-int(group["sample_count"]), hashlib.sha256(f"{seed}:{group['prefix']}".encode()).hexdigest()),
    )
    counts = {split: 0 for split in RATIOS}
    result = {}
    for group in ordered:
        prefix = group["prefix"]
        size = int(group["sample_count"])
        choice = min(RATIOS, key=lambda split: (abs((counts[split] + size) - targets[split]), split))
        result[prefix] = choice
        counts[choice] += size
    return result


def overlap_by_key(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    buckets: dict[str, set[str]] = {}
    for row in rows:
        buckets.setdefault(row[key], set()).add(row["split"])
    return [{"key": key_value, "splits": sorted(splits)} for key_value, splits in sorted(buckets.items()) if len(splits) > 1]
