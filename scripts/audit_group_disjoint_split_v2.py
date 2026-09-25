#!/usr/bin/env python3
"""Independently audit a Scope 10 group-disjoint V2 manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(source_manifest: Path, v2_manifest: Path) -> dict[str, Any]:
    source = json.loads(source_manifest.read_text(encoding="utf-8"))["samples"]
    v2_document = json.loads(v2_manifest.read_text(encoding="utf-8"))
    v2 = v2_document["samples"]
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    source_keys = [(row.get("source"), row.get("image")) for row in source]
    v2_keys = [(row.get("source"), row.get("image")) for row in v2]
    if len(v2) != len(source):
        errors.append({"code": "sample_count_mismatch", "source": len(source), "v2": len(v2)})
    if len(set(v2_keys)) != len(v2_keys):
        errors.append({"code": "sample_duplicate"})
    if set(source_keys) != set(v2_keys):
        errors.append({"code": "sample_loss_or_extra", "missing": len(set(source_keys) - set(v2_keys)), "extra": len(set(v2_keys) - set(source_keys))})
    split_values = {"train", "val", "test", "quarantine"}
    if any(row.get("assignment_status") not in {"ASSIGNED", "QUARANTINED"} for row in v2):
        errors.append({"code": "invalid_assignment_status"})
    if any(row.get("split") not in split_values for row in v2):
        errors.append({"code": "invalid_split_value"})
    if any((row.get("assignment_status") == "ASSIGNED") != (row.get("split") in {"train", "val", "test"}) for row in v2):
        errors.append({"code": "assignment_split_inconsistency"})
    verified_groups: dict[str, set[str]] = defaultdict(set)
    for row in v2:
        if row.get("provenance_class") == "VERIFIED_SEQUENCE_GROUP":
            verified_groups[row.get("group", "")].add(row.get("split", ""))
    split_groups = {group: sorted(splits) for group, splits in verified_groups.items() if len(splits) != 1}
    if split_groups:
        errors.append({"code": "verified_group_split", "groups": split_groups})
    source_path_splits: dict[str, set[str]] = defaultdict(set)
    source_hash_splits: dict[str, set[str]] = defaultdict(set)
    for row in v2:
        if row.get("split") not in {"train", "val", "test"}:
            continue
        source_path_splits[str(row.get("image"))].add(row["split"])
        source_hash_splits[str(row.get("image_hash"))].add(row["split"])
    path_overlap = {key: sorted(value) for key, value in source_path_splits.items() if len(value) > 1}
    hash_overlap = {key: sorted(value) for key, value in source_hash_splits.items() if len(value) > 1}
    if path_overlap:
        errors.append({"code": "exact_source_path_overlap", "count": len(path_overlap)})
    if hash_overlap:
        errors.append({"code": "exact_source_hash_overlap", "count": len(hash_overlap)})
    unverified = [row for row in v2 if row.get("provenance_class") == "GROUP_UNVERIFIED"]
    if any(row.get("split") != "quarantine" for row in unverified):
        errors.append({"code": "unverified_not_quarantined", "count": sum(row.get("split") != "quarantine" for row in unverified)})
    if unverified:
        warnings.append({"code": "provenance_unknown", "sample_count": len(unverified), "group_count": len({row.get('group') for row in unverified})})
    assigned = [row for row in v2 if row.get("split") in {"train", "val", "test"}]
    counts = {split: sum(row.get("split") == split for row in assigned) for split in ("train", "val", "test")}
    total_assigned = len(assigned)
    ratios = {split: counts[split] / total_assigned for split in counts} if total_assigned else {split: 0.0 for split in counts}
    metadata = v2_document.get("metadata", {})
    if metadata.get("source_manifest_sha256") != sha256(source_manifest):
        errors.append({"code": "source_manifest_hash_mismatch"})
    if metadata.get("grouping_rule_version") is None or metadata.get("split_algorithm_version") is None:
        errors.append({"code": "missing_algorithm_metadata"})
    return {
        "status": "PASS" if not errors else "FAIL",
        "source_manifest_sha256": sha256(source_manifest),
        "v2_manifest_sha256": sha256(v2_manifest),
        "source_sample_count": len(source),
        "v2_sample_count": len(v2),
        "assigned_sample_count": total_assigned,
        "quarantined_sample_count": len(v2) - total_assigned,
        "split_counts": counts,
        "split_ratios_over_assigned": ratios,
        "verified_group_count": len(verified_groups),
        "verified_group_overlap": len(split_groups),
        "exact_source_path_overlap": len(path_overlap),
        "exact_source_hash_overlap": len(hash_overlap),
        "group_unverified_sample_count": len(unverified),
        "group_unverified_group_count": len({row.get("group") for row in unverified}),
        "independent_validation_claim": False if unverified else True,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=Path("data/processed/drone-single-class/manifest.json"))
    parser.add_argument("--v2-manifest", type=Path, default=Path("data/processed/drone-single-class-v2/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/drone-single-class-v2/audit.json"))
    args = parser.parse_args()
    report = audit(args.source_manifest, args.v2_manifest)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
