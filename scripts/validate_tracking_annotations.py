#!/usr/bin/env python3
"""Validate frame-level tracking manifests and identity annotations.

The validator deliberately keeps detector output and tracker output out of the
ground-truth format.  A row describes one manually verified object identity in
one source frame:

    sequence_id,frame_id,track_id,class_id,x1,y1,x2,y2

An empty annotation file is valid as a preparation artifact, but is reported
as ``DATA READY — IDENTITY ANNOTATION PENDING`` rather than as verified GT.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


MANIFEST_FIELDS = {
    "sequence_id",
    "frame_id",
    "source_frame_index",
    "timestamp",
    "image_width",
    "image_height",
    "source_reference",
}
ANNOTATION_FIELDS = {
    "sequence_id",
    "frame_id",
    "track_id",
    "class_id",
    "x1",
    "y1",
    "x2",
    "y2",
}


def _issue(code: str, message: str, *, row: int | None = None, severity: str = "error") -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "message": message, "severity": severity}
    if row is not None:
        item["row"] = row
    return item


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def _int(value: str, field: str, issues: list[dict[str, Any]], row: int) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        issues.append(_issue("invalid_integer", f"{field} must be an integer; got {value!r}", row=row))
        return None


def _float(value: str, field: str, issues: list[dict[str, Any]], row: int) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        issues.append(_issue("invalid_number", f"{field} must be numeric; got {value!r}", row=row))
        return None
    if not math.isfinite(number):
        issues.append(_issue("non_finite_number", f"{field} must be finite; got {value!r}", row=row))
        return None
    return number


def validate(
    manifest_path: str | Path,
    annotations_path: str | Path,
    *,
    identity_verified: bool = False,
) -> dict[str, Any]:
    """Validate one sequence and return a JSON-serializable report."""

    manifest_path = Path(manifest_path)
    annotations_path = Path(annotations_path)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not manifest_path.exists():
        return {
            "status": "FAIL",
            "identity_ground_truth": "pending",
            "errors": [_issue("manifest_missing", f"Manifest does not exist: {manifest_path}")],
            "warnings": [],
            "counts": {},
        }
    if not annotations_path.exists():
        return {
            "status": "FAIL",
            "identity_ground_truth": "pending",
            "errors": [_issue("annotations_missing", f"Annotations do not exist: {annotations_path}")],
            "warnings": [],
            "counts": {},
        }

    manifest_rows, manifest_headers = _read_csv(manifest_path)
    annotation_rows, annotation_headers = _read_csv(annotations_path)
    missing_manifest = sorted(MANIFEST_FIELDS - set(manifest_headers))
    missing_annotations = sorted(ANNOTATION_FIELDS - set(annotation_headers))
    if missing_manifest:
        errors.append(_issue("manifest_schema", f"Manifest is missing fields: {', '.join(missing_manifest)}"))
    if missing_annotations:
        errors.append(_issue("annotation_schema", f"Annotations are missing fields: {', '.join(missing_annotations)}"))

    expected_sequence: str | None = None
    frame_ids: set[int] = set()
    dimensions: dict[int, tuple[int, int]] = {}
    timestamps: list[float] = []
    missing_timestamps = 0

    if not missing_manifest:
        for csv_row, item in enumerate(manifest_rows, start=2):
            sequence_id = (item.get("sequence_id") or "").strip()
            if not sequence_id:
                errors.append(_issue("missing_sequence_id", "sequence_id is required", row=csv_row))
            elif expected_sequence is None:
                expected_sequence = sequence_id
            elif sequence_id != expected_sequence:
                errors.append(_issue("multiple_sequences", f"Expected sequence {expected_sequence!r}, got {sequence_id!r}", row=csv_row))

            frame_id = _int(item.get("frame_id", ""), "frame_id", errors, csv_row)
            if frame_id is None:
                continue
            if frame_id in frame_ids:
                errors.append(_issue("duplicate_frame_id", f"frame_id {frame_id} appears more than once", row=csv_row))
            frame_ids.add(frame_id)

            width = _int(item.get("image_width", ""), "image_width", errors, csv_row)
            height = _int(item.get("image_height", ""), "image_height", errors, csv_row)
            if width is not None and height is not None:
                if width <= 0 or height <= 0:
                    errors.append(_issue("invalid_dimensions", "image dimensions must be positive", row=csv_row))
                dimensions[frame_id] = (width, height)

            raw_timestamp = (item.get("timestamp") or "").strip()
            if not raw_timestamp:
                missing_timestamps += 1
            else:
                timestamp = _float(raw_timestamp, "timestamp", errors, csv_row)
                if timestamp is not None:
                    timestamps.append(timestamp)

        if missing_timestamps:
            warnings.append(_issue("timestamp_missing", f"{missing_timestamps} manifest frame(s) have no timestamp", severity="warning"))
        if len(timestamps) > 1:
            for previous, current in zip(timestamps, timestamps[1:]):
                if current <= previous:
                    errors.append(_issue("timestamp_not_increasing", f"Timestamps must be strictly increasing; got {previous} then {current}"))
                    break

    seen_tracks: set[tuple[int, int]] = set()
    annotation_frame_ids: set[int] = set()
    if not missing_annotations:
        for csv_row, item in enumerate(annotation_rows, start=2):
            sequence_id = (item.get("sequence_id") or "").strip()
            if sequence_id and expected_sequence and sequence_id != expected_sequence:
                errors.append(_issue("wrong_sequence_id", f"Annotation sequence {sequence_id!r} does not match {expected_sequence!r}", row=csv_row))

            frame_id = _int(item.get("frame_id", ""), "frame_id", errors, csv_row)
            track_id = _int(item.get("track_id", ""), "track_id", errors, csv_row)
            class_id = _int(item.get("class_id", ""), "class_id", errors, csv_row)
            if frame_id is None or track_id is None or class_id is None:
                continue
            annotation_frame_ids.add(frame_id)
            if frame_id not in frame_ids:
                errors.append(_issue("annotation_frame_missing", f"Annotation references unknown frame_id {frame_id}", row=csv_row))
                continue
            if track_id <= 0:
                errors.append(_issue("invalid_track_id", "track_id must be a positive integer", row=csv_row))
            if class_id != 0:
                errors.append(_issue("invalid_class_id", f"class_id must be 0 for the drone class; got {class_id}", row=csv_row))
            key = (frame_id, track_id)
            if key in seen_tracks:
                errors.append(_issue("duplicate_track_in_frame", f"track_id {track_id} is duplicated in frame {frame_id}", row=csv_row))
            seen_tracks.add(key)

            box = [_float(item.get(name, ""), name, errors, csv_row) for name in ("x1", "y1", "x2", "y2")]
            if any(value is None for value in box):
                continue
            x1, y1, x2, y2 = box
            width, height = dimensions[frame_id]
            if x2 <= x1 or y2 <= y1:
                errors.append(_issue("invalid_bbox", "bbox must have positive width and height", row=csv_row))
            if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
                errors.append(_issue("bbox_out_of_bounds", f"bbox {box} exceeds frame bounds {width}x{height}", row=csv_row))

    if not annotation_rows and not missing_annotations:
        warnings.append(_issue("identity_annotation_pending", "No identity annotations are present; this is not MOT ground truth", severity="warning"))
    identity_ground_truth = "pending" if not annotation_rows else ("verified" if identity_verified and not errors else "unverified")
    if annotation_rows and not identity_verified:
        warnings.append(_issue("identity_annotation_unverified", "Identity rows exist but were not declared manually verified", severity="warning"))

    if errors:
        status = "FAIL"
    elif not annotation_rows:
        status = "DATA READY — IDENTITY ANNOTATION PENDING"
    elif warnings:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    return {
        "status": status,
        "identity_ground_truth": identity_ground_truth,
        "manifest": str(manifest_path.resolve()),
        "annotations": str(annotations_path.resolve()),
        "sequence_id": expected_sequence,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "manifest_frames": len(manifest_rows),
            "unique_frame_ids": len(frame_ids),
            "annotation_rows": len(annotation_rows),
            "annotation_frames": len(annotation_frame_ids),
            "unique_tracks": len({track for _, track in seen_tracks}),
            "missing_timestamps": missing_timestamps,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--identity-verified", action="store_true")
    args = parser.parse_args()
    report = validate(args.manifest, args.annotations, identity_verified=args.identity_verified)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
