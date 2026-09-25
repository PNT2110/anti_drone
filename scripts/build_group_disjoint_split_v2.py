#!/usr/bin/env python3
"""Build a manifest-only, group-disjoint V2 split without touching V1 files."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


RATIOS = {"train": 0.70, "val": 0.20, "test": 0.10}
GROUPING_RULE_VERSION = "scope10-rgbt-sequence-group-v1"
SPLIT_ALGORITHM_VERSION = "scope10-seeded-shuffle-largest-deficit-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_sample(sample: dict[str, Any]) -> str:
    """Classify provenance without treating filename absence as independence."""

    if sample.get("source") == "base" and str(sample.get("group", "")).startswith("base:RGBT_"):
        return "VERIFIED_SEQUENCE_GROUP"
    return "GROUP_UNVERIFIED"


def assign_verified_groups(samples: list[dict[str, Any]], seed: int) -> dict[str, str]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        if sample["provenance_class"] == "VERIFIED_SEQUENCE_GROUP":
            groups[sample["group"]].append(sample)
    ordered = sorted(groups)
    random.Random(seed).shuffle(ordered)
    total = sum(len(values) for values in groups.values())
    targets = {split: total * ratio for split, ratio in RATIOS.items()}
    current = Counter()
    assignment: dict[str, str] = {}
    for group in ordered:
        size = len(groups[group])
        split = max(RATIOS, key=lambda value: (targets[value] - current[value], -list(RATIOS).index(value)))
        assignment[group] = split
        current[split] += size
    return assignment


def build_manifest(source_manifest: Path, output: Path, seed: int = 42) -> dict[str, Any]:
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    source_samples = source["samples"]
    samples = []
    for original in source_samples:
        sample = dict(original)
        sample["provenance_class"] = classify_sample(sample)
        sample["assignment_status"] = ""
        sample["split"] = ""
        samples.append(sample)
    group_assignment = assign_verified_groups(samples, seed)
    for sample in samples:
        if sample["provenance_class"] == "VERIFIED_SEQUENCE_GROUP":
            sample["split"] = group_assignment[sample["group"]]
            sample["assignment_status"] = "ASSIGNED"
        else:
            sample["split"] = "quarantine"
            sample["assignment_status"] = "QUARANTINED"
    split_counts = Counter(sample["split"] for sample in samples)
    assigned = sum(split_counts[split] for split in RATIOS)
    group_counts = Counter(sample["provenance_class"] for sample in samples)
    verified_groups = {sample["group"] for sample in samples if sample["provenance_class"] == "VERIFIED_SEQUENCE_GROUP"}
    unverified_groups = {sample["group"] for sample in samples if sample["provenance_class"] == "GROUP_UNVERIFIED"}
    metadata = {
        "dataset_id": "drone-single-class-v2",
        "version": "v2",
        "source_manifest": str(source_manifest),
        "source_manifest_sha256": sha256(source_manifest),
        "source_v1_split_registry_sha256": sha256(source_manifest.parent / "split_registry.json"),
        "source_v1_audit_sha256": sha256(source_manifest.parent / "audit.json"),
        "grouping_rule_version": GROUPING_RULE_VERSION,
        "split_algorithm_version": SPLIT_ALGORITHM_VERSION,
        "seed": seed,
        "target_ratio": RATIOS,
        "sample_count": len(samples),
        "group_count": len({sample["group"] for sample in samples}),
        "verified_group_count": len(verified_groups),
        "group_unverified_count": len(unverified_groups),
        "provenance_class_counts": dict(group_counts),
        "assigned_sample_count": assigned,
        "quarantined_sample_count": split_counts["quarantine"],
        "split_counts": {split: split_counts[split] for split in (*RATIOS, "quarantine")},
        "split_ratios_over_assigned": {split: (split_counts[split] / assigned if assigned else 0.0) for split in RATIOS},
        "verified_independent_image_count": 0,
        "policy": {
            "VERIFIED_SEQUENCE_GROUP": "assign intact to exactly one train/val/test split",
            "VERIFIED_INDEPENDENT_IMAGE": "none present in V1; not inferred from filename absence",
            "GROUP_UNVERIFIED": "quarantine; never claim independent validation/test",
        },
        "v1_preserved": True,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps({"metadata": metadata, "samples": samples}, indent=2) + "\n", encoding="utf-8")
    registry = {
        "dataset_id": "drone-single-class-v2",
        "seed": seed,
        "grouping_rule_version": GROUPING_RULE_VERSION,
        "split_algorithm_version": SPLIT_ALGORITHM_VERSION,
        "target_ratio": RATIOS,
        "actual_counts": {split: split_counts[split] for split in (*RATIOS, "quarantine")},
        "actual_ratio_over_assigned": {split: (split_counts[split] / assigned if assigned else 0.0) for split in RATIOS},
        "verified_group_counts": {split: len({sample["group"] for sample in samples if sample["split"] == split and sample["provenance_class"] == "VERIFIED_SEQUENCE_GROUP"}) for split in RATIOS},
        "sample_count": len(samples),
        "assigned_sample_count": assigned,
        "quarantined_sample_count": split_counts["quarantine"],
        "verified_group_count": len(verified_groups),
        "group_unverified_count": len(unverified_groups),
        "group_overlap": "not trusted as audit evidence; see independent audit.json",
    }
    (output / "split_registry.json").write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=Path("data/processed/drone-single-class/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/drone-single-class-v2"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    metadata = build_manifest(args.source_manifest, args.output, args.seed)
    print(json.dumps({"status": "PASS", "output": str(args.output.resolve()), "metadata": metadata}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
