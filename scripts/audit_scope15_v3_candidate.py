"""Audit the Scope 15 V3 candidate from the materialized files on disk.

This audit is deliberately independent of the materializer's in-memory list.
It is the gate before a YOLO data.yaml is allowed to be written.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v3-candidate"
V2 = ROOT / "data/processed/drone-single-class-v2/manifest.json"
S13_MAPPING = ROOT / ".runtime/scope13/rgbt_archive_mapping.csv"
OUT = ROOT / ".runtime/scope15/direct_disk_audit.json"
DATASET_OUT = DATASET / "direct_disk_audit.json"
EXPECTED = {"train": 12142, "val": 8237, "test": 9848}
EXPECTED_QUARANTINE = {"samples": 6505, "groups": 4172}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def audit_label(path: Path) -> tuple[int, list[str]]:
    objects = 0
    errors: list[str] = []
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
            errors.append(f"{path}:{line_no}: class/bbox outside normalized range")
        if values[3] <= 0 or values[4] <= 0:
            errors.append(f"{path}:{line_no}: non-positive bbox size")
        epsilon = 1e-6
        if values[1] - values[3] / 2 < -epsilon or values[1] + values[3] / 2 > 1 + epsilon or values[2] - values[4] / 2 < -epsilon or values[2] + values[4] / 2 > 1 + epsilon:
            errors.append(f"{path}:{line_no}: bbox exceeds image bounds")
        objects += 1
    return objects, errors


def archive_partition(member: str) -> str | None:
    match = re.search(r"(?:^|/)Anti-UAV300/data/Anti-UAV300/(train|val|test)/", member)
    return match.group(1) if match else None


def main() -> int:
    if not DATASET.is_dir():
        raise RuntimeError(f"BLOCKED: candidate dataset missing: {DATASET}")
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    mapping_rows = list(csv.DictReader(S13_MAPPING.open(encoding="utf-8")))
    mapping_by_image = {row["image"]: row for row in mapping_rows}
    quarantine_ids = {(row["source"], row["image"]) for row in v2["samples"] if row.get("assignment_status") == "QUARANTINED"}
    assigned_count = sum(row.get("assignment_status") == "ASSIGNED" for row in v2["samples"])
    errors: list[str] = []
    counts: Counter[str] = Counter()
    split_paths: dict[str, set[str]] = defaultdict(set)
    split_hashes: dict[str, set[str]] = defaultdict(set)
    group_splits: dict[str, set[str]] = defaultdict(set)
    sequence_splits: dict[str, set[str]] = defaultdict(set)
    prefix_splits: dict[str, set[str]] = defaultdict(set)
    sample_ids: set[str] = set()
    output_ids: set[tuple[str, str, str]] = set()
    source_ids: set[tuple[str, str]] = set()
    label_objects = 0
    image_bytes = 0
    label_bytes = 0

    if len(mapping_rows) != assigned_count or assigned_count != 30227:
        errors.append(f"mapping/assigned count mismatch: mapping={len(mapping_rows)}, assigned={assigned_count}")
    if len(manifest.get("samples", [])) != 30227:
        errors.append(f"manifest sample count {len(manifest.get('samples', []))} != 30227")

    for row in manifest.get("samples", []):
        split = row.get("candidate_split")
        counts[split] += 1
        sample_id = row.get("sample_id")
        if sample_id in sample_ids:
            errors.append(f"duplicate sample_id: {sample_id}")
        sample_ids.add(sample_id)
        output_id = (split, row.get("output_image", ""), row.get("output_label", ""))
        if output_id in output_ids:
            errors.append(f"duplicate output id: {output_id}")
        output_ids.add(output_id)
        source_id = (row.get("source", ""), row.get("source_image", ""))
        if source_id in source_ids:
            errors.append(f"duplicate source id: {source_id}")
        source_ids.add(source_id)
        if row.get("assignment_status") != "ASSIGNED":
            errors.append(f"non-assigned row in candidate: {sample_id}")
        if (row.get("source", ""), Path(row.get("source_image", "")).name) in quarantine_ids:
            errors.append(f"quarantine row leaked: {sample_id}")
        if row.get("provenance_status") != "CONFIRMED_SOURCE_SEQUENCE_ARCHIVE_MEMBER; SESSION_DISJOINT_UNVERIFIED":
            errors.append(f"unexpected provenance status: {sample_id}")

        source_map = mapping_by_image.get(row.get("source_image", ""))
        if source_map is None:
            errors.append(f"missing Scope 13 mapping: {sample_id}")
        else:
            source_partition = archive_partition(source_map["source_video_member"])
            for field in ("source_archive", "source_video_member", "source_annotation_member", "source_sequence_directory", "source_frame_index", "modality", "candidate_prefix"):
                if row.get(field) is None or row.get(field) == "":
                    errors.append(f"missing provenance field {field}: {sample_id}")
            if source_partition != split or row.get("original_source_partition") != source_partition:
                errors.append(f"original partition boundary violation: {sample_id}")
            if row.get("source_video_member") != source_map["source_video_member"] or row.get("source_frame_index") != int(source_map["source_frame_index"]):
                errors.append(f"source mapping mismatch: {sample_id}")
            sequence_splits[source_map["source_sequence_id"]].add(split)
            prefix_splits[source_map["source_session_prefix"]].add(split)
            group_splits[source_map["source_sequence_id"]].add(split)

        image = DATASET / row.get("output_image", "")
        label = DATASET / row.get("output_label", "")
        source_image = Path(row.get("source_image", ""))
        source_label = Path(row.get("source_label", ""))
        for path, kind in ((image, "output image"), (label, "output label"), (source_image, "source image"), (source_label, "source label")):
            if not path.is_file() or path.is_symlink():
                errors.append(f"bad {kind}: {path}")
        if image.is_file() and source_image.is_file():
            image_hash = sha256(image)
            source_hash = sha256(source_image)
            split_paths[split].add(str(source_image))
            split_hashes[split].add(source_hash)
            image_bytes += image.stat().st_size
            if image_hash != source_hash or image_hash != row.get("output_image_sha256") or image_hash != row.get("image_hash"):
                errors.append(f"image hash mismatch: {sample_id}")
        if label.is_file() and source_label.is_file():
            output_label_hash = sha256(label)
            source_label_hash = sha256(source_label)
            label_bytes += label.stat().st_size
            if output_label_hash != source_label_hash or output_label_hash != row.get("output_label_sha256") or source_label_hash != row.get("source_label_sha256"):
                errors.append(f"label hash mismatch: {sample_id}")
            objects, label_errors = audit_label(label)
            label_objects += objects
            errors.extend(label_errors)

    for split, expected in EXPECTED.items():
        if counts[split] != expected:
            errors.append(f"{split} count {counts[split]} != {expected}")
        for kind in ("images", "labels"):
            directory = DATASET / kind / split
            if not directory.is_dir():
                errors.append(f"missing directory: {directory}")
    for name, groups in (("sequence", sequence_splits), ("prefix", prefix_splits), ("group", group_splits)):
        for identifier, splits in groups.items():
            if len(splits) != 1:
                errors.append(f"{name} crosses split: {identifier} -> {sorted(splits)}")
    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        if split_paths[left] & split_paths[right]:
            errors.append(f"source path overlap: {left}/{right}")
        if split_hashes[left] & split_hashes[right]:
            errors.append(f"source hash overlap: {left}/{right}")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "dataset": str(DATASET),
        "sample_count": len(manifest.get("samples", [])),
        "assigned_sample_count": assigned_count,
        "quarantine_excluded": EXPECTED_QUARANTINE,
        "split_counts": dict(counts),
        "sequence_count": len(sequence_splits),
        "prefix_count": len(prefix_splits),
        "groups_crossing_split": sum(len(value) > 1 for value in group_splits.values()),
        "label_object_count": label_objects,
        "materialized_image_bytes": image_bytes,
        "materialized_label_bytes": label_bytes,
        "data_yaml_present": (DATASET / "data.yaml").is_file(),
        "errors": errors,
    }
    write_json(OUT, report)
    write_json(DATASET_OUT, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
