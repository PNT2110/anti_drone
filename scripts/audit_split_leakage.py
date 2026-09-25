#!/usr/bin/env python3
"""Audit image-split independence at group, frame and provenance levels."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def audit(manifest_path: str | Path) -> dict[str, Any]:
    samples = json.loads(Path(manifest_path).read_text(encoding="utf-8"))["samples"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    keys: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in samples:
        stem = Path(row["image"]).stem
        match = re.search(r"(\d+)$", stem)
        source_frame_index = int(match.group(1)) if match else None
        modality = "visible" if "_visible_" in stem else "infrared" if "_infrared_" in stem else "other"
        enriched = row | {"modality": modality, "source_frame_index": source_frame_index, "basename": Path(row["image"]).name}
        groups[row["group"]].append(enriched)
        keys[f"{row['group']}|{modality}|{source_frame_index}"].append(enriched)

    def cross_split(values: list[dict[str, Any]]) -> bool:
        return len({value["split"] for value in values}) > 1

    group_overlap = [(key, values) for key, values in groups.items() if cross_split(values)]
    source_frame_overlap = [(key, values) for key, values in keys.items() if cross_split(values)]
    provenance_counts = {}
    for field in ("image_hash", "image", "basename"):
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in samples:
            buckets[row[field] if field != "basename" else Path(row["image"]).name].append(row)
        provenance_counts[field] = sum(cross_split(values) for values in buckets.values())

    neighbor_pairs: list[dict[str, Any]] = []
    close_pairs = 0
    for key, values in groups.items():
        by_modality: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for value in values:
            by_modality[value["modality"]].append(value)
        for modality, rows in by_modality.items():
            rows.sort(key=lambda value: value["source_frame_index"] if value["source_frame_index"] is not None else -1)
            for first, second in zip(rows, rows[1:]):
                if first["split"] == second["split"]:
                    continue
                delta = second["source_frame_index"] - first["source_frame_index"]
                if delta <= 10:
                    close_pairs += 1
                if delta <= 10 and len(neighbor_pairs) < 12:
                    neighbor_pairs.append({
                        "group": key,
                        "modality": modality,
                        "first": {"basename": first["basename"], "split": first["split"], "source_frame_index": first["source_frame_index"]},
                        "second": {"basename": second["basename"], "split": second["split"], "source_frame_index": second["source_frame_index"]},
                        "source_frame_delta": delta,
                    })

    processed_text = Path(manifest_path).read_text(encoding="utf-8")
    v_drone_occurrences = processed_text.count("V_DRONE_001")
    status = "CONFIRMED TEMPORAL LEAKAGE" if group_overlap and close_pairs else "NO CONFIRMED TEMPORAL LEAKAGE"
    return {
        "manifest": str(Path(manifest_path).resolve()),
        "sample_count": len(samples),
        "split_counts": dict(Counter(row["split"] for row in samples)),
        "group_count": len(groups),
        "group_overlap_count": len(group_overlap),
        "group_overlap_rows": sum(len(values) for _, values in group_overlap),
        "same_source_frame_cross_split_count": len(source_frame_overlap),
        "cross_split_neighbor_pairs": close_pairs,
        "neighbor_definition": "consecutive available samples within a group+modality, source-frame-index delta <= 10",
        "neighbor_examples": neighbor_pairs,
        "cross_split_provenance_collisions": provenance_counts,
        "v_drone_001_occurrences_in_processed_manifest": v_drone_occurrences,
        "status": status,
        "interpretation": "Group IDs are generated from RGBT filename tokens with modality and trailing frame number removed; the split generator hashes individual samples, not groups.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
