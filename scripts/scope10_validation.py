"""Pure validation helpers for Scope 10 temporal provenance artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _error(code: str, **fields: Any) -> dict[str, Any]:
    return {"code": code, **fields}


def validate_sequence(sequence: dict[str, Any], sequence_dir: Path) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    sequence_id = sequence.get("sequence_id")
    manifest_path = sequence_dir / "frame_manifest.csv"
    annotation_path = sequence_dir / "annotations" / "source_boxes.csv"
    if not sequence_id:
        errors.append(_error("missing_sequence_id"))
    if not manifest_path.exists():
        errors.append(_error("missing_frame_manifest"))
        return {"sequence_id": sequence_id, "status": "FAIL", "errors": errors, "warnings": warnings}
    manifest = read_csv(manifest_path)
    frame_ids = [int(row["frame_id"]) for row in manifest]
    source_indices = [int(row["source_frame_index"]) for row in manifest]
    timestamps = [float(row["timestamp"]) for row in manifest]
    expected = list(range(1, len(manifest) + 1))
    if frame_ids != expected:
        errors.append(_error("frame_order_or_duplicate", expected_first=1, actual_head=frame_ids[:5]))
    if source_indices != list(range(len(manifest))):
        errors.append(_error("source_frame_order_or_duplicate"))
    if any(timestamps[index] >= timestamps[index + 1] for index in range(len(timestamps) - 1)):
        errors.append(_error("timestamp_not_monotonic"))
    for row in manifest:
        if row.get("sequence_id") != sequence_id:
            errors.append(_error("manifest_sequence_id_mismatch", frame_id=row.get("frame_id")))
            break
        if int(row["image_width"]) <= 0 or int(row["image_height"]) <= 0:
            errors.append(_error("invalid_resolution", frame_id=row.get("frame_id")))
            break
    expected_frames = sequence.get("frame_count")
    if expected_frames is not None and int(expected_frames) != len(manifest):
        errors.append(_error("frame_count_mismatch", metadata=expected_frames, manifest=len(manifest)))
    annotation_rows = read_csv(annotation_path) if annotation_path.exists() else []
    if not annotation_path.exists():
        errors.append(_error("missing_source_annotations"))
    annotation_frame_ids: set[int] = set()
    for row in annotation_rows:
        frame_id = int(row["frame_id"])
        annotation_frame_ids.add(frame_id)
        if row.get("sequence_id") != sequence_id:
            errors.append(_error("annotation_sequence_id_mismatch", frame_id=frame_id))
        if frame_id not in set(frame_ids):
            errors.append(_error("annotation_frame_missing_from_manifest", frame_id=frame_id))
        x1, y1, x2, y2 = (float(row[key]) for key in ("x1", "y1", "x2", "y2"))
        width = int(manifest[frame_id - 1]["image_width"]) if 0 < frame_id <= len(manifest) else 0
        height = int(manifest[frame_id - 1]["image_height"]) if 0 < frame_id <= len(manifest) else 0
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            errors.append(_error("invalid_annotation_box", frame_id=frame_id))
    source_key = (sequence.get("source_archive"), sequence.get("source_member"))
    if not all(source_key):
        warnings.append(_error("provenance_unknown", field="source_archive_or_member"))
    status = "PASS" if not errors else "FAIL"
    return {
        "sequence_id": sequence_id,
        "status": status,
        "frames": len(manifest),
        "annotation_rows": len(annotation_rows),
        "annotated_frames": len(annotation_frame_ids),
        "source_key": list(source_key),
        "errors": errors,
        "warnings": warnings,
    }


def validate_dataset_manifest(dataset: dict[str, Any], sequence_dirs: dict[str, Path]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    sequences = dataset.get("sequences", [])
    ids = [item.get("sequence_id") for item in sequences]
    if len(ids) != len(set(ids)):
        errors.append(_error("duplicate_sequence_id"))
    source_keys: dict[tuple[Any, Any], str] = {}
    member_keys: dict[tuple[Any, Any], str] = {}
    sequence_reports = []
    frame_hashes: dict[str, str] = {}
    for item in sequences:
        sequence_id = item.get("sequence_id")
        if sequence_id not in sequence_dirs:
            errors.append(_error("missing_sequence_directory", sequence_id=sequence_id))
            continue
        sequence_report = validate_sequence(item, sequence_dirs[sequence_id])
        sequence_reports.append(sequence_report)
        errors.extend({**error, "sequence_id": sequence_id} for error in sequence_report["errors"])
        warnings.extend({**warning, "sequence_id": sequence_id} for warning in sequence_report["warnings"])
        key = (item.get("source_archive"), item.get("source_member"))
        if key in source_keys:
            errors.append(_error("same_source_video_collision", sequence_id=sequence_id, other_sequence=source_keys[key], source_key=list(key)))
        elif all(key):
            source_keys[key] = sequence_id
        member_key = (item.get("source_archive"), item.get("source_member_sha256"))
        if all(member_key):
            if member_key in member_keys:
                errors.append(_error("duplicate_source_member", sequence_id=sequence_id, other_sequence=member_keys[member_key]))
            else:
                member_keys[member_key] = sequence_id
        for value in item.get("frame_hashes", []):
            if value in frame_hashes and frame_hashes[value] != sequence_id:
                errors.append(_error("exact_duplicate_leakage", sequence_id=sequence_id, other_sequence=frame_hashes[value], frame_hash=value))
            frame_hashes[value] = sequence_id
        if item.get("training_overlap_status") != "CONFIRMED_SOURCE_DISJOINT":
            if "independent_validation" in item.get("permission", []):
                errors.append(_error("unverified_independent_permission", sequence_id=sequence_id))
            warnings.append(_error("provenance_unknown", sequence_id=sequence_id))
        if item.get("training_overlap_status") == "CONFIRMED_SOURCE_DISJOINT" and "independent_validation" not in item.get("permission", []):
            errors.append(_error("missing_independent_permission", sequence_id=sequence_id))
        if item.get("identity_status") != "IDENTITY VERIFIED" and "identity_metric_ready" in item.get("permission", []):
            errors.append(_error("unverified_identity_metric_permission", sequence_id=sequence_id))
    return {
        "status": "PASS" if not errors else "FAIL",
        "sequence_count": len(sequences),
        "sequence_reports": sequence_reports,
        "errors": errors,
        "warnings": warnings,
        "collision_classes": {
            "exact_duplicate_leakage": sum(error["code"] == "exact_duplicate_leakage" for error in errors),
            "same_source_video_leakage": sum(error["code"] == "same_source_video_collision" for error in errors),
            "same_sequence_leakage": sum(error["code"] == "duplicate_sequence_id" for error in errors),
            "provenance_unknown": sum(warning["code"] == "provenance_unknown" for warning in warnings),
        },
    }
