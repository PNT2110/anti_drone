"""Audit Scope 12's materialized dataset directly from disk."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v2-executable"
V2 = ROOT / "data/processed/drone-single-class-v2/manifest.json"
OUTPUT = DATASET / "executable_dataset_audit.json"
EXPECTED = {"train": 21168, "val": 6096, "test": 2963}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_labels(path: Path) -> tuple[int, list[str]]:
    errors = []
    objects = 0
    for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="strict").splitlines(), 1):
        fields = raw.split()
        if len(fields) != 5:
            errors.append(f"{path}:{line_no}: expected 5 fields")
            continue
        try:
            values = [float(value) for value in fields]
        except ValueError:
            errors.append(f"{path}:{line_no}: non-numeric label")
            continue
        if values[0] != 0 or any(not 0.0 <= value <= 1.0 for value in values[1:]):
            errors.append(f"{path}:{line_no}: class/bbox outside valid normalized range")
        if values[3] <= 0 or values[4] <= 0:
            errors.append(f"{path}:{line_no}: non-positive bbox size")
        # Labels are stored with six decimal places.  A box whose calculated
        # edge is 1.0000005 (or -0.0000005) is the expected decimal rounding
        # of an image-boundary edge, not an out-of-image annotation.  No label
        # is rewritten or clamped.
        epsilon = 1e-6
        if values[1] - values[3] / 2 < -epsilon or values[1] + values[3] / 2 > 1 + epsilon or values[2] - values[4] / 2 < -epsilon or values[2] + values[4] / 2 > 1 + epsilon:
            errors.append(f"{path}:{line_no}: bbox exceeds image bounds")
        objects += 1
    return objects, errors


def main() -> int:
    if not DATASET.is_dir():
        raise RuntimeError(f"BLOCKED: dataset missing: {DATASET}")
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    assigned = [row for row in v2["samples"] if row.get("assignment_status") == "ASSIGNED"]
    if len(manifest["samples"]) != len(assigned):
        raise RuntimeError("BLOCKED: executable manifest does not match assigned row count")

    errors: list[str] = []
    counts = Counter()
    output_ids = set()
    source_ids = set()
    group_splits: dict[str, set[str]] = defaultdict(set)
    source_paths: dict[str, set[str]] = defaultdict(set)
    source_hashes: dict[str, set[str]] = defaultdict(set)
    quarantine_ids = {
        (row["source"], row["image"], row["image_hash"])
        for row in v2["samples"] if row.get("assignment_status") == "QUARANTINED"
    }
    label_objects = 0
    for row in manifest["samples"]:
        split = row["split"]
        counts[split] += 1
        image = DATASET / row["output_image"]
        label = DATASET / row["output_label"]
        source_id = (row["source"], row["source_image"], row["source_image_hash"])
        output_id = (split, row["output_image"], row["output_label"])
        if output_id in output_ids:
            errors.append(f"duplicate output id: {output_id}")
        output_ids.add(output_id)
        if source_id in source_ids:
            errors.append(f"duplicate source id: {source_id}")
        source_ids.add(source_id)
        if source_id in quarantine_ids:
            errors.append(f"quarantine row leaked: {source_id}")
        group_splits[row["source_group"]].add(split)
        source_paths[split].add(row["source_image"])
        source_hashes[split].add(row["source_image_hash"])
        if not image.is_file() or image.is_symlink():
            errors.append(f"bad output image: {image}")
        if not label.is_file() or label.is_symlink():
            errors.append(f"bad output label: {label}")
        if image.is_file() and sha256_file(image) != row["source_image_hash"]:
            errors.append(f"output image hash mismatch: {image}")
        source_image = Path(row["source_image"])
        source_label = Path(row["source_label"])
        if not source_image.is_file() or sha256_file(source_image) != row["source_image_hash"]:
            errors.append(f"source image hash mismatch: {source_image}")
        if label.is_file():
            if not source_label.is_file() or sha256_file(source_label) != row["output_label_sha256"]:
                errors.append(f"output label differs from source label: {label}")
            objects, label_errors = audit_labels(label)
            label_objects += objects
            errors.extend(label_errors)
    for split, expected in EXPECTED.items():
        if counts[split] != expected:
            errors.append(f"{split} count {counts[split]} != {expected}")
        if not (DATASET / "images" / split).is_dir() or not (DATASET / "labels" / split).is_dir():
            errors.append(f"missing split directory: {split}")
    for group, splits in group_splits.items():
        if len(splits) != 1:
            errors.append(f"group crosses split: {group} -> {sorted(splits)}")
    for left in EXPECTED:
        for right in EXPECTED:
            if left >= right:
                continue
            if source_paths[left] & source_paths[right]:
                errors.append(f"source path overlap: {left}/{right}")
            if source_hashes[left] & source_hashes[right]:
                errors.append(f"source hash overlap: {left}/{right}")
    data_yaml = DATASET / "data.yaml"
    if not data_yaml.is_file() or str(DATASET) not in data_yaml.read_text(encoding="utf-8"):
        errors.append("data.yaml missing or does not point to executable dataset")
    report = {
        "status": "PASS" if not errors else "FAIL",
        "dataset": str(DATASET),
        "sample_count": len(manifest["samples"]),
        "split_counts": dict(counts),
        "group_count": len(group_splits),
        "groups_crossing_split": sum(len(splits) > 1 for splits in group_splits.values()),
        "label_object_count": label_objects,
        "quarantine_leak_count": sum("quarantine row leaked" in error for error in errors),
        "source_path_overlap_count": sum("source path overlap" in error for error in errors),
        "source_hash_overlap_count": sum("source hash overlap" in error for error in errors),
        "errors": errors,
    }
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
