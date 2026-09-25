#!/usr/bin/env python3
"""Validate human identity review state and export GT only after review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.prepare_identity_review import EVIDENCE_FIELDS
from scripts.validate_tracking_annotations import validate as validate_tracking_annotations


REVIEW_FIELDS = {
    "sequence_id", "frame_id", "timestamp", "source_box_reference",
    "candidate_identity", "review_status", "review_note",
}
SOURCE_FIELDS = {"sequence_id", "frame_id", "source_label", "x1", "y1", "x2", "y2", "source_annotation_reference"}
ALLOWED_STATUSES = {"PENDING", "NEEDS_REVIEW", "VERIFIED", "REJECTED"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _positive_int(value: str) -> bool:
    return value.strip().isdigit() and int(value.strip()) > 0


def _apply_evidence(
    review_rows: list[dict[str, str]],
    evidence_path: Path,
    source_frame_ids: set[int],
    *,
    require_full_coverage: bool,
) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    evidence_rows = _read_csv(evidence_path)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    headers = set(evidence_rows[0]) if evidence_rows else set()
    if headers != set(EVIDENCE_FIELDS):
        errors.append({"code": "evidence_schema", "message": f"Expected evidence fields: {EVIDENCE_FIELDS}"})

    ranges: list[tuple[int, int, int, dict[str, str]]] = []
    covered: set[int] = set()
    for row_number, row in enumerate(evidence_rows, start=2):
        try:
            frame_start = int(row.get("frame_start", ""))
            frame_end = int(row.get("frame_end", ""))
        except ValueError:
            errors.append({"code": "invalid_evidence_range", "row": row_number})
            continue
        if frame_start > frame_end:
            errors.append({"code": "invalid_evidence_range", "row": row_number, "frame_start": frame_start, "frame_end": frame_end})
            continue
        if frame_start < min(source_frame_ids, default=1) or frame_end > max(source_frame_ids, default=0):
            errors.append({"code": "evidence_out_of_range", "row": row_number, "frame_start": frame_start, "frame_end": frame_end})
            continue
        status = row.get("review_status", "").strip().upper()
        if status not in ALLOWED_STATUSES:
            errors.append({"code": "invalid_evidence_status", "row": row_number, "status": status})
        if status == "VERIFIED" and not _positive_int(row.get("assigned_track_id", "")):
            errors.append({"code": "verified_assigned_track_id_missing", "row": row_number})
        if status != "PENDING":
            missing = [field for field in ("review_note", "review_timestamp", "reviewer_reference") if not row.get(field, "").strip()]
            if missing:
                errors.append({"code": "reviewer_evidence_missing", "row": row_number, "fields": missing})
        for previous_start, previous_end, previous_row, _ in ranges:
            if frame_start <= previous_end and frame_end >= previous_start:
                errors.append({"code": "overlapping_evidence_segment", "row": row_number, "previous_row": previous_row})
        ranges.append((frame_start, frame_end, row_number, row))
        covered.update(range(frame_start, frame_end + 1))

    missing_frames = sorted(source_frame_ids - covered)
    if missing_frames:
        item = {"code": "evidence_missing_frames", "frames": len(missing_frames), "first_frame": missing_frames[0], "last_frame": missing_frames[-1]}
        if require_full_coverage:
            errors.append(item)
        else:
            warnings.append(item)

    effective = [dict(row) for row in review_rows]
    effective_by_frame = {int(row["frame_id"]): row for row in effective if row.get("frame_id", "").isdigit()}
    for frame_start, frame_end, _, evidence in ranges:
        status = evidence.get("review_status", "").strip().upper()
        for frame_id in range(frame_start, frame_end + 1):
            row = effective_by_frame.get(frame_id)
            if row is None:
                continue
            row["review_status"] = status
            row["candidate_identity"] = evidence.get("assigned_track_id", "").strip()
            row["review_note"] = evidence.get("review_note", "").strip()

    summary = {
        "path": str(evidence_path.resolve()),
        "segments": len(evidence_rows),
        "covered_frames": len(covered & source_frame_ids),
        "source_frames": len(source_frame_ids),
        "missing_frames": missing_frames,
    }
    return effective, errors, warnings, summary


def validate_review(
    review_manifest_path: str | Path,
    source_boxes_path: str | Path,
    ground_truth_path: str | Path,
    *,
    export_ground_truth: bool = False,
    manifest_path: str | Path | None = None,
    evidence_path: str | Path | None = None,
) -> dict[str, Any]:
    review_manifest_path = Path(review_manifest_path)
    source_boxes_path = Path(source_boxes_path)
    ground_truth_path = Path(ground_truth_path)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    review_rows = _read_csv(review_manifest_path)
    source_rows = _read_csv(source_boxes_path)
    review_headers = set(review_rows[0]) if review_rows else set()
    source_headers = set(source_rows[0]) if source_rows else set()
    missing_review = sorted(REVIEW_FIELDS - review_headers)
    missing_source = sorted(SOURCE_FIELDS - source_headers)
    if missing_review:
        errors.append({"code": "review_schema", "message": f"Missing review fields: {missing_review}"})
    if missing_source:
        errors.append({"code": "source_schema", "message": f"Missing source fields: {missing_source}"})

    source_by_frame = {int(row["frame_id"]): row for row in source_rows if row.get("frame_id", "").isdigit()}
    frame_ids: set[int] = set()
    evidence_summary = None
    if evidence_path is not None and not missing_review and not missing_source:
        review_rows, evidence_errors, evidence_warnings, evidence_summary = _apply_evidence(
            review_rows, Path(evidence_path), set(source_by_frame), require_full_coverage=export_ground_truth
        )
        errors.extend(evidence_errors)
        warnings.extend(evidence_warnings)
    verified_ids: set[int] = set()
    status_counts = Counter()
    pending_rows: list[int] = []
    uncertain_rows: list[int] = []
    if not missing_review:
        for row_number, row in enumerate(review_rows, start=2):
            try:
                frame_id = int(row["frame_id"])
            except ValueError:
                errors.append({"code": "invalid_frame_id", "row": row_number})
                continue
            if frame_id in frame_ids:
                errors.append({"code": "duplicate_review_frame", "row": row_number, "frame_id": frame_id})
            frame_ids.add(frame_id)
            source = source_by_frame.get(frame_id)
            if source is None:
                errors.append({"code": "missing_source_annotation", "row": row_number, "frame_id": frame_id})
            elif row["source_box_reference"] != source["source_annotation_reference"]:
                errors.append({"code": "source_provenance_mismatch", "row": row_number, "frame_id": frame_id})
            status = row["review_status"].strip().upper()
            status_counts[status] += 1
            if status not in ALLOWED_STATUSES:
                errors.append({"code": "invalid_review_status", "row": row_number, "status": status})
                continue
            candidate = row["candidate_identity"].strip()
            if status == "VERIFIED":
                if not candidate.isdigit() or int(candidate) <= 0:
                    errors.append({"code": "verified_identity_missing", "row": row_number, "frame_id": frame_id})
                else:
                    verified_ids.add(int(candidate))
                if not row["review_note"].strip():
                    errors.append({"code": "verified_review_note_missing", "row": row_number, "frame_id": frame_id})
            elif status == "PENDING":
                pending_rows.append(frame_id)
            elif status == "NEEDS_REVIEW":
                uncertain_rows.append(frame_id)

    expected_frames = set(source_by_frame)
    if frame_ids != expected_frames:
        errors.append({"code": "review_frame_coverage", "message": f"Review frames={len(frame_ids)} source frames={len(expected_frames)}"})
    all_verified = bool(review_rows) and not errors and status_counts == Counter({"VERIFIED": len(review_rows)})
    exported = False
    if export_ground_truth and all_verified:
        fields = ["sequence_id", "frame_id", "track_id", "class_id", "x1", "y1", "x2", "y2"]
        review_by_frame = {int(row["frame_id"]): row for row in review_rows}
        with ground_truth_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for frame_id in sorted(source_by_frame):
                source = source_by_frame[frame_id]
                review = review_by_frame[frame_id]
                writer.writerow({
                    "sequence_id": source["sequence_id"], "frame_id": frame_id,
                    "track_id": int(review["candidate_identity"]), "class_id": 0,
                    "x1": source["x1"], "y1": source["y1"], "x2": source["x2"], "y2": source["y2"],
                })
        exported = True
    if export_ground_truth and not all_verified:
        warnings.append({"code": "ground_truth_export_blocked", "message": "Official ground truth remains unchanged until every review row is VERIFIED."})
    if pending_rows:
        warnings.append({"code": "identity_review_pending", "frames": len(pending_rows), "first_frame": pending_rows[0], "last_frame": pending_rows[-1]})
    if uncertain_rows:
        warnings.append({"code": "identity_review_uncertain", "frames": len(uncertain_rows), "first_frame": uncertain_rows[0], "last_frame": uncertain_rows[-1]})

    status = "PASS" if all_verified and not errors else "IDENTITY ANNOTATION PENDING" if not errors else "FAIL"
    ground_truth_validation = None
    if exported and manifest_path is not None:
        ground_truth_validation = validate_tracking_annotations(manifest_path, ground_truth_path, identity_verified=True)
    report: dict[str, Any] = {
        "status": status,
        "review_manifest": str(review_manifest_path.resolve()),
        "source_boxes": str(source_boxes_path.resolve()),
        "ground_truth": str(ground_truth_path.resolve()),
        "evidence": str(Path(evidence_path).resolve()) if evidence_path is not None else None,
        "counts": {
            "source_frames": len(source_rows), "review_rows": len(review_rows),
            "pending_frames": status_counts["PENDING"], "needs_review_frames": status_counts["NEEDS_REVIEW"],
            "rejected_frames": status_counts["REJECTED"], "verified_frames": status_counts["VERIFIED"],
            "verified_track_ids": len(verified_ids),
        },
        "status_counts": dict(status_counts),
        "errors": errors,
        "warnings": warnings,
        "ground_truth_exported": exported,
        "ground_truth_validation": ground_truth_validation,
        "evidence_summary": evidence_summary,
        "provenance": {
            "review_manifest_sha256": _sha256(review_manifest_path),
            "source_boxes_sha256": _sha256(source_boxes_path),
            "evidence_sha256": _sha256(Path(evidence_path)) if evidence_path is not None else None,
            "identity_status": "VERIFIED" if all_verified else "PENDING",
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-manifest", type=Path, required=True)
    parser.add_argument("--source-boxes", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export-ground-truth", action="store_true")
    args = parser.parse_args()
    report = validate_review(args.review_manifest, args.source_boxes, args.ground_truth, export_ground_truth=args.export_ground_truth, manifest_path=args.manifest, evidence_path=args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
