#!/usr/bin/env python3
"""Prepare one continuous Halmstad sequence without extracting the archive."""

from __future__ import annotations

import argparse
import csv
import json
import tarfile
from pathlib import Path

import cv2


def _extract_member(archive: Path, member: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as handle:
        extracted = handle.extractfile(member)
        if extracted is None:
            raise FileNotFoundError(f"Archive member not found: {member}")
        destination.write_bytes(extracted.read())


def prepare(archive: Path, video_member: str, labels_member: str, output: Path, sequence_id: str) -> dict[str, object]:
    video_path = output / "source" / Path(video_member).name
    labels_path = output / "source" / Path(labels_member).name
    _extract_member(archive, video_member, video_path)
    _extract_member(archive, labels_member, labels_path)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open extracted video: {video_path}")
    reported_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    decoded_frames = 0
    while True:
        ok, _ = capture.read()
        if not ok:
            break
        decoded_frames += 1
    capture.release()
    if reported_frames != decoded_frames:
        raise RuntimeError(f"Video frame count mismatch: reported={reported_frames}, decoded={decoded_frames}")
    if fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid video metadata: fps={fps}, size={width}x{height}")

    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "frame_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "sequence_id", "frame_id", "source_frame_index", "timestamp",
            "image_width", "image_height", "source_reference", "annotation_reference", "split",
        ])
        writer.writeheader()
        for frame_index in range(decoded_frames):
            writer.writerow({
                "sequence_id": sequence_id,
                "frame_id": frame_index + 1,
                "source_frame_index": frame_index,
                "timestamp": f"{frame_index / fps:.9f}",
                "image_width": width,
                "image_height": height,
                "source_reference": video_member,
                "annotation_reference": labels_member,
                "split": "source_archive_unassigned",
            })

    annotations_path = output / "annotations" / "ground_truth.csv"
    annotations_path.parent.mkdir(parents=True, exist_ok=True)
    with annotations_path.open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=["sequence_id", "frame_id", "track_id", "class_id", "x1", "y1", "x2", "y2"]).writeheader()

    metadata = {
        "sequence_id": sequence_id,
        "sequence_type": "continuous_video",
        "status": "DATA READY — IDENTITY ANNOTATION PENDING",
        "archive": str(archive.resolve()),
        "video_member": video_member,
        "labels_member": labels_member,
        "extracted_video": str(video_path.resolve()),
        "extracted_labels": str(labels_path.resolve()),
        "frame_count": decoded_frames,
        "reported_frame_count": reported_frames,
        "decoded_frame_count": decoded_frames,
        "fps": fps,
        "timestamp_source": "source_video_fps",
        "width": width,
        "height": height,
        "split_status": "SPLIT_UNVERIFIED",
        "identity_ground_truth": "pending",
        "notes": [
            "Only the selected video and its label sidecar were extracted; the archive was not expanded wholesale.",
            "The MATLAB groundTruth sidecar is retained for future identity/box normalization; no pseudo IDs were generated.",
        ],
    }
    (output / "sequence.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--video-member", required=True)
    parser.add_argument("--labels-member", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sequence-id", default="halmstad_v_drone_001")
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.video_member, args.labels_member, args.output, args.sequence_id), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
