#!/usr/bin/env python3
"""Create a human-review manifest from source boxes without assigning IDs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REVIEW_FIELDS = [
    "sequence_id",
    "frame_id",
    "timestamp",
    "source_box_reference",
    "candidate_identity",
    "review_status",
    "review_note",
]
EVIDENCE_FIELDS = [
    "sequence_id",
    "frame_start",
    "frame_end",
    "assigned_track_id",
    "review_status",
    "review_note",
    "review_timestamp",
    "reviewer_reference",
]
SOURCE_FIELDS = {"sequence_id", "frame_id", "source_label", "x1", "y1", "x2", "y2", "source_annotation_reference"}


def prepare(source_boxes_path: str | Path, manifest_path: str | Path, output_path: str | Path) -> dict[str, object]:
    with Path(source_boxes_path).open("r", encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    with Path(manifest_path).open("r", encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    if not source_rows:
        raise ValueError("source_boxes.csv is empty")
    if set(source_rows[0]) != SOURCE_FIELDS:
        raise ValueError(f"Unexpected source box schema: {list(source_rows[0])}")
    if len(source_rows) != len(manifest_rows):
        raise ValueError(f"Source boxes ({len(source_rows)}) and manifest ({len(manifest_rows)}) do not align")

    rows = []
    for index, (source, frame) in enumerate(zip(source_rows, manifest_rows), start=1):
        if int(source["frame_id"]) != int(frame["frame_id"]) or int(frame["frame_id"]) != index:
            raise ValueError(f"Frame alignment failed at review row {index}")
        rows.append({
            "sequence_id": frame["sequence_id"],
            "frame_id": frame["frame_id"],
            "timestamp": frame["timestamp"],
            "source_box_reference": source["source_annotation_reference"],
            "candidate_identity": "",
            "review_status": "PENDING",
            "review_note": "HUMAN REVIEW PENDING",
        })
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    evidence_path = output_path.parent / "identity_review_evidence.csv"
    batch_ranges = (
        [(1, 60), (61, 120), (121, 180), (181, 240), (241, 301)]
        if len(rows) == 301
        else [(1, len(rows))]
    )
    with evidence_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVIDENCE_FIELDS)
        writer.writeheader()
        for frame_start, frame_end in batch_ranges:
            writer.writerow({
                "sequence_id": rows[0]["sequence_id"],
                "frame_start": frame_start,
                "frame_end": frame_end,
                "assigned_track_id": "",
                "review_status": "PENDING",
                "review_note": "",
                "review_timestamp": "",
                "reviewer_reference": "",
            })
    summary = {
        "status": "HUMAN REVIEW PENDING",
        "sequence_id": rows[0]["sequence_id"],
        "frames": len(rows),
        "reviewed_frames": 0,
        "pending_frames": len(rows),
        "verified_track_ids": 0,
        "output": str(output_path.resolve()),
        "evidence_template": str(evidence_path.resolve()),
        "review_segments": [{"frame_start": start, "frame_end": end} for start, end in batch_ranges],
        "allowed_review_statuses": ["PENDING", "NEEDS_REVIEW", "VERIFIED", "REJECTED"],
        "note": "No candidate identity or track ID is populated by this preparation step.",
    }
    (output_path.parent / "identity_review_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output_path.parent / "IDENTITY_REVIEW_WORKFLOW.md").write_text(
        "# Identity review workflow\n\n"
        "Review `source_boxes_overlay.mp4` with `scripts/review_identity_sequence.py` (pause/step) or sequentially.\n"
        "Record one evidence decision per batch in `identity_review_evidence.csv`; keep the per-frame manifest as a preparation artifact.\n\n"
        "- `PENDING`: not yet reviewed.\n"
        "- `NEEDS_REVIEW`: visual continuity or identity is uncertain.\n"
        "- `VERIFIED`: reviewer confirmed the physical drone identity across the whole segment; set a positive `assigned_track_id`, timestamp, reviewer reference, and evidence note.\n"
        "- `REJECTED`: source box is not usable for identity ground truth.\n\n"
        "Do not use tracker output as identity. Run `scripts/validate_identity_review.py --evidence identity_review_evidence.csv` after editing.\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-boxes", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_boxes, args.manifest, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
