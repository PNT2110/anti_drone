#!/usr/bin/env python3
"""Inspect and convert the Halmstad MATLAB groundTruth sidecar.

The files are MATLAB v5 files containing MATLAB ``MCOS`` opaque objects. The
converter reconstructs the nested FileWrapper workspace emitted by MATLAB
R2019b, then exports source boxes only. It never invents ``track_id`` values.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
import tempfile
import zlib
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat


def _unwrap(value: Any) -> Any:
    while isinstance(value, np.ndarray) and value.dtype == object and value.size == 1:
        value = value.flat[0]
    return value


def _text(value: Any) -> str:
    value = _unwrap(value)
    if isinstance(value, np.ndarray):
        if value.dtype.kind in "US":
            return "".join(str(part) for part in value.ravel())
        if value.dtype.kind == "u" and value.size:
            return bytes(int(part) for part in value.ravel()).decode("utf-8", errors="replace")
    return str(value)


def _compressed_payloads(path: Path) -> tuple[bytes, list[bytes]]:
    raw = path.read_bytes()
    header = raw[:128]
    if not header.startswith(b"MATLAB 5.0 MAT-file"):
        raise ValueError("Not a MATLAB v5 MAT-file")
    payloads: list[bytes] = []
    offset = 128
    while offset + 8 <= len(raw):
        data_type, size = struct.unpack_from("<II", raw, offset)
        if data_type != 15:  # miCOMPRESSED
            offset += 8 + size
            continue
        compressed = raw[offset + 8 : offset + 8 + size]
        payloads.append(zlib.decompress(compressed))
        offset += 8 + size
    if len(payloads) < 2:
        raise ValueError(f"Expected at least two compressed MAT elements, found {len(payloads)}")
    return header, payloads


def _load_nested_ground_truth(path: Path) -> tuple[Any, bytes, list[bytes]]:
    header, payloads = _compressed_payloads(path)
    # The second top-level variable is __function_workspace__, a uint8 matrix
    # containing another serialized MAT workspace. SciPy can decode the outer
    # matrix, after which the nested matrix can be decoded normally.
    with tempfile.NamedTemporaryFile(suffix=".mat") as outer:
        outer.write(header + payloads[1])
        outer.flush()
        workspace = loadmat(outer.name, variable_names=["__function_workspace__"])["__function_workspace__"]
    nested_bytes = np.asarray(workspace, dtype=np.uint8).reshape(-1).tobytes()
    if nested_bytes[:4] != b"\x00\x01IM":
        raise ValueError("Unexpected MATLAB nested workspace header")
    with tempfile.NamedTemporaryFile(suffix=".mat") as nested:
        nested.write(header + nested_bytes[8:])
        nested.flush()
        decoded = loadmat(nested.name, variable_names=["__function_workspace__"])["__function_workspace__"]
    opaque = decoded[0, 0]["MCOS"][0]
    metadata = opaque["_ObjectMetadata"].reshape(-1)
    for item in metadata:
        if isinstance(item, np.ndarray) and item.dtype.names and "LabelData" in item.dtype.names:
            return item, nested_bytes, payloads
    raise ValueError("Could not find a groundTruth object with LabelData")


def inspect_sidecar(path: str | Path) -> dict[str, Any]:
    """Extract the usable groundTruth structure without modifying the MAT file."""

    path = Path(path)
    header, payloads = _compressed_payloads(path)
    ground_truth, nested_bytes, _ = _load_nested_ground_truth(path)
    data_source = _unwrap(ground_truth["DataSource"])
    label_definitions = _unwrap(ground_truth["LabelDefinitions"])
    label_data = _unwrap(ground_truth["LabelData"])
    frame_count = int(label_data.shape[0])

    timestamps_ms: np.ndarray | None = None
    # The FileWrapper metadata contains the 301-element millisecond vector.
    # Match it by shape and strict monotonicity instead of relying on an
    # opaque-object index.
    opaque = None
    with tempfile.NamedTemporaryFile(suffix=".mat") as outer:
        outer.write(header + payloads[1])
        outer.flush()
        workspace = loadmat(outer.name, variable_names=["__function_workspace__"])["__function_workspace__"]
    nested = np.asarray(workspace, dtype=np.uint8).reshape(-1).tobytes()
    with tempfile.NamedTemporaryFile(suffix=".mat") as nested_file:
        nested_file.write(header + nested[8:])
        nested_file.flush()
        decoded = loadmat(nested_file.name, variable_names=["__function_workspace__"])["__function_workspace__"]
    opaque = decoded[0, 0]["MCOS"][0]
    for item in opaque["_ObjectMetadata"].reshape(-1):
        value = _unwrap(item)
        if isinstance(value, np.ndarray) and value.dtype.kind in "fiu" and value.shape == (frame_count, 1):
            candidate = value.astype(float).reshape(-1)
            if candidate[0] == 0 and np.all(np.diff(candidate) > 0):
                timestamps_ms = candidate
                break
    if timestamps_ms is None:
        raise ValueError("Could not locate monotonic source timestamps")

    class_names = [_text(label_definitions["Name"][i, 0]) for i in range(label_definitions.shape[0])]
    boxes_by_label: dict[str, list[list[list[float]]]] = {}
    for name in class_names:
        rows: list[list[list[float]]] = []
        for index in range(frame_count):
            value = label_data[name][index, 0]
            if isinstance(value, np.ndarray) and value.size:
                rows.append(np.asarray(value, dtype=float).reshape(-1, 4).tolist())
            else:
                rows.append([])
        boxes_by_label[name] = rows

    drone_boxes = np.asarray([row[0] for row in boxes_by_label["DRONE"] if row], dtype=float)
    xyxy = drone_boxes.copy()
    xyxy[:, 2:] += xyxy[:, :2]
    bounds_ok = bool(
        len(drone_boxes)
        and np.all(drone_boxes[:, :2] >= 0)
        and np.all(drone_boxes[:, 2:] > 0)
        and np.all(xyxy[:, 0] < 640)
        and np.all(xyxy[:, 1] < 512)
        and np.all(xyxy[:, 2] <= 640)
        and np.all(xyxy[:, 3] <= 512)
    )
    label_data_fields = list(label_data.dtype.names or ())
    source_path = _text(data_source["Source"])
    return {
        "mat_version": "MATLAB v5, little-endian IM, version 0x0100",
        "mat_header": header[:116].decode("ascii", errors="replace").rstrip(),
        "matlab_source_path": source_path,
        "ground_truth_class": "groundTruth",
        "label_definitions": class_names,
        "label_data_fields": label_data_fields,
        "frame_count": frame_count,
        "timestamps_ms": [float(value) for value in timestamps_ms],
        "timestamp_range_ms": [float(timestamps_ms[0]), float(timestamps_ms[-1])],
        "timestamp_step_ms": float(np.median(np.diff(timestamps_ms))),
        "coordinate_format": "xywh_pixels",
        "coordinate_format_evidence": "DRONE values have four fields; raw MATLAB workspace contains Rectangle; xyxy interpretation makes x2<x1 for source rows.",
        "boxes_by_label": boxes_by_label,
        "drone_box_count": int(sum(len(row) for row in boxes_by_label["DRONE"])),
        "drone_annotated_frames": int(sum(bool(row) for row in boxes_by_label["DRONE"])),
        "multiple_drone_frames": int(sum(len(row) > 1 for row in boxes_by_label["DRONE"])),
        "all_drone_boxes_in_640x512_bounds": bounds_ok,
        "identity_metadata": False,
        "identity_metadata_reason": "LabelData fields are Time plus class rectangles; no track/id field is present.",
        "source_annotation_reference": "gTruth.LabelData.DRONE[row_index_zero_based]",
        "nested_workspace_bytes": len(nested_bytes),
    }


def convert_source_boxes(
    sidecar_path: str | Path,
    manifest_path: str | Path,
    output_path: str | Path,
    sequence_id: str,
) -> dict[str, Any]:
    report = inspect_sidecar(sidecar_path)
    with Path(manifest_path).open("r", encoding="utf-8", newline="") as handle:
        manifest = list(csv.DictReader(handle))
    count = int(report["frame_count"])
    if len(manifest) != count:
        raise ValueError(f"Manifest has {len(manifest)} rows but MATLAB LabelData has {count} rows")
    timestamps = report["timestamps_ms"]
    for index, row in enumerate(manifest):
        if int(row["frame_id"]) != index + 1 or int(row["source_frame_index"]) != index:
            raise ValueError(f"Frame alignment failed at row {index}: expected frame_id={index + 1}, source_frame_index={index}")
        if abs(float(row["timestamp"]) - timestamps[index] / 1000.0) > 1e-4:
            raise ValueError(f"Timestamp alignment failed at frame {index + 1}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["sequence_id", "frame_id", "source_label", "x1", "y1", "x2", "y2", "source_annotation_reference"]
    written = 0
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, boxes in enumerate(report["boxes_by_label"]["DRONE"]):
            for box_index, box in enumerate(boxes):
                x1, y1, width, height = [float(value) for value in box]
                x2, y2 = x1 + width, y1 + height
                if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1 or x2 > 640 or y2 > 512:
                    raise ValueError(f"Source bbox out of bounds at frame {index + 1}: {box}")
                writer.writerow({
                    "sequence_id": sequence_id,
                    "frame_id": index + 1,
                    "source_label": "DRONE",
                    "x1": f"{x1:.6f}",
                    "y1": f"{y1:.6f}",
                    "x2": f"{x2:.6f}",
                    "y2": f"{y2:.6f}",
                    "source_annotation_reference": f"{Path(sidecar_path).name}:gTruth.LabelData.DRONE[row={index},box={box_index}]",
                })
                written += 1
    return report | {
        "converted_rows": written,
        "converted_output": str(output_path.resolve()),
        "frame_id_mapping": "manifest frame_id = MATLAB LabelData row index + 1; source_frame_index = row index",
        "track_id_status": "NOT PRESENT — identity annotation pending",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mat", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--sequence-id", default="halmstad_v_drone_001")
    args = parser.parse_args()
    report = convert_source_boxes(args.mat, args.manifest, args.output, args.sequence_id)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    # Do not store every box twice in the inspection report.
    report_for_json = report | {"boxes_by_label": {name: {"frames": len(rows), "boxes": sum(len(row) for row in rows)} for name, rows in report["boxes_by_label"].items()}}
    args.report.write_text(json.dumps(report_for_json, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report_for_json, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
