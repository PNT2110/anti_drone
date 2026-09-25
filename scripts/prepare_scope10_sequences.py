#!/usr/bin/env python3
"""Prepare a small, source-referenced temporal validation set without bulk extraction."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import subprocess
import tarfile
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.convert_halmstad_sidecar import _load_nested_ground_truth, _text, _unwrap


SELECTIONS = (
    ("sequence_002", "halmstad_v_drone_046", "Halmstad-Drone/Data/Video_V/V_DRONE_046.mp4", "Halmstad-Drone/Data/Video_V/V_DRONE_046_LABELS.mat"),
    ("sequence_003", "halmstad_v_drone_048", "Halmstad-Drone/Data/Video_V/V_DRONE_048.mp4", "Halmstad-Drone/Data/Video_V/V_DRONE_048_LABELS.mat"),
    ("sequence_004", "halmstad_v_drone_045", "Halmstad-Drone/Data/Video_V/V_DRONE_045.mp4", "Halmstad-Drone/Data/Video_V/V_DRONE_045_LABELS.mat"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def member_sha256(archive: Path, member: str) -> str:
    digest = hashlib.sha256()
    with tarfile.open(archive) as handle:
        source = handle.extractfile(member)
        if source is None:
            raise FileNotFoundError(member)
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_member(archive: Path, member: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as handle:
        source = handle.extractfile(member)
        if source is None:
            raise FileNotFoundError(member)
        with destination.open("wb") as target:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                target.write(chunk)


def probe_video(video: Path) -> dict[str, Any]:
    command = [
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=nb_read_frames,width,height,r_frame_rate,avg_frame_rate",
        "-of", "json", str(video),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    stream = json.loads(result.stdout)["streams"][0]
    frame_count = int(stream["nb_read_frames"])
    fps = float(Fraction(stream.get("avg_frame_rate") or stream["r_frame_rate"]))
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-map", "0:v:0", "-f", "null", "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    if decode.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed for {video}: {decode.stderr[-1000:]}")
    return {
        "frame_count": frame_count,
        "fps": fps,
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "frame_rate_raw": stream.get("avg_frame_rate") or stream["r_frame_rate"],
        "decode_check": "PASS",
    }


def write_frame_manifest(output: Path, sequence_id: str, video_member: str, labels_member: str, video: dict[str, Any]) -> Path:
    path = output / "frame_manifest.csv"
    fields = [
        "sequence_id", "frame_id", "source_frame_index", "timestamp",
        "image_width", "image_height", "source_reference", "annotation_reference", "split",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for source_index in range(video["frame_count"]):
            writer.writerow({
                "sequence_id": sequence_id,
                "frame_id": source_index + 1,
                "source_frame_index": source_index,
                "timestamp": f"{source_index / video['fps']:.9f}",
                "image_width": video["width"],
                "image_height": video["height"],
                "source_reference": video_member,
                "annotation_reference": labels_member,
                "split": "temporal_validation_unassigned",
            })
    return path


def normalize_sidecar_boxes(sidecar: Path, manifest: Path, output: Path, sequence_id: str, width: int, height: int) -> dict[str, Any]:
    ground_truth, _, _ = _load_nested_ground_truth(sidecar)
    definitions = _unwrap(ground_truth["LabelDefinitions"])
    label_data = _unwrap(ground_truth["LabelData"])
    class_names = [_text(definitions["Name"][index, 0]) for index in range(definitions.shape[0])]
    if "DRONE" not in class_names:
        raise ValueError(f"DRONE source label missing in {sidecar}")
    manifest_rows = list(csv.DictReader(manifest.open("r", encoding="utf-8", newline="")))
    if len(manifest_rows) != label_data.shape[0]:
        raise ValueError(f"Frame alignment failed: video manifest={len(manifest_rows)}, LabelData={label_data.shape[0]}")
    fields = ["sequence_id", "frame_id", "source_label", "x1", "y1", "x2", "y2", "source_annotation_reference"]
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    annotated_frames = 0
    multiple_frames = 0
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, manifest_row in enumerate(manifest_rows):
            boxes = _unwrap(label_data["DRONE"][index, 0])
            if not isinstance(boxes, np.ndarray) or not boxes.size:
                continue
            boxes = np.asarray(boxes, dtype=float).reshape(-1, 4)
            annotated_frames += 1
            multiple_frames += int(len(boxes) > 1)
            for box_index, values in enumerate(boxes):
                x1, y1, box_width, box_height = map(float, values)
                x2, y2 = x1 + box_width, y1 + box_height
                if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1 or x2 > width or y2 > height:
                    raise ValueError(f"Source bbox out of bounds at frame {index + 1}: {values.tolist()}")
                writer.writerow({
                    "sequence_id": sequence_id,
                    "frame_id": int(manifest_row["frame_id"]),
                    "source_label": "DRONE",
                    "x1": f"{x1:.6f}", "y1": f"{y1:.6f}", "x2": f"{x2:.6f}", "y2": f"{y2:.6f}",
                    "source_annotation_reference": f"{sidecar.name}:gTruth.LabelData.DRONE[row={index},box={box_index}]",
                })
                rows += 1
    return {
        "frame_count": int(label_data.shape[0]),
        "converted_rows": rows,
        "drone_annotated_frames": annotated_frames,
        "multiple_drone_frames": multiple_frames,
        "label_definitions": class_names,
        "coordinate_format": "xywh_pixels converted to xyxy",
        "identity_metadata": False,
        "identity_metadata_reason": "LabelData contains class rectangles and Time fields only; no stable track/id field is present.",
        "timestamp_alignment": "frame row index aligned; timestamps sourced from video FPS because this sidecar's DataSource.TimeStamps is not a per-frame monotonic vector",
    }


def prepare_one(archive: Path, output: Path, selection: tuple[str, str, str, str], archive_sha256: str | None) -> dict[str, Any]:
    sequence_dir, sequence_id, video_member, labels_member = selection
    destination = output / sequence_dir
    source_dir = destination / "source"
    video_path = source_dir / Path(video_member).name
    labels_path = source_dir / Path(labels_member).name
    extract_member(archive, video_member, video_path)
    extract_member(archive, labels_member, labels_path)
    video = probe_video(video_path)
    manifest = write_frame_manifest(destination, sequence_id, video_member, labels_member, video)
    annotation_path = destination / "annotations" / "source_boxes.csv"
    annotation_report = normalize_sidecar_boxes(labels_path, manifest, annotation_path, sequence_id, video["width"], video["height"])
    review_dir = destination / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_status = {
        "sequence_id": sequence_id,
        "identity_status": "IDENTITY REVIEW REQUIRED" if annotation_report["converted_rows"] else "IDENTITY UNAVAILABLE",
        "source_boxes": annotation_report["converted_rows"],
        "frames": video["frame_count"],
        "objects": annotation_report["converted_rows"],
        "frames_requiring_review": annotation_report["drone_annotated_frames"],
        "source_ids": False,
        "reason": annotation_report["identity_metadata_reason"],
        "review_scope": "status and workload only; no identity assignment in Scope 10",
    }
    (review_dir / "identity_status.json").write_text(json.dumps(review_status, indent=2) + "\n", encoding="utf-8")
    metadata = {
        "sequence_id": sequence_id,
        "sequence_type": "continuous_video",
        "source_archive": str(archive.relative_to(Path.cwd())) if archive.is_relative_to(Path.cwd()) else str(archive.resolve()),
        "source_archive_sha256": archive_sha256,
        "source_member": video_member,
        "source_member_sha256": member_sha256(archive, video_member),
        "annotation_member": labels_member,
        "annotation_member_sha256": member_sha256(archive, labels_member),
        "frame_count": video["frame_count"],
        "fps": video["fps"],
        "resolution": [video["width"], video["height"]],
        "timestamp_source": "source_video_avg_frame_rate",
        "annotation_status": "SOURCE_BOXES_NORMALIZED",
        "identity_status": review_status["identity_status"],
        "training_overlap_status": "PROVENANCE_UNVERIFIED",
        "permission": ["diagnostic_only"],
        "split_status": "SPLIT_UNVERIFIED",
        "notes": [
            "Selected by predeclared archive inventory rule: three largest visible V_DRONE members with matching MAT sidecars.",
            "Only this video and its MAT sidecar were extracted; no archive was expanded wholesale.",
            "Source annotations contain boxes but no stable identity field; no pseudo IDs were created.",
        ],
    }
    (destination / "sequence.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata | {"video_probe": video, "annotation_report": annotation_report, "review_status": review_status}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("data/import_data_rar/Halmstad-Drone.tar"))
    parser.add_argument("--output", type=Path, default=Path("data/tracking_eval"))
    args = parser.parse_args()
    archive_sha = sha256(args.archive) if args.archive.stat().st_size <= 1024 * 1024 * 1024 else None
    results = [prepare_one(args.archive, args.output, selection, archive_sha) for selection in SELECTIONS]
    print(json.dumps({"status": "PASS", "archive_sha256": archive_sha, "sequences": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
