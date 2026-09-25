import csv
import json

from scripts.validate_tracking_annotations import validate


FIELDS = ["sequence_id", "frame_id", "source_frame_index", "timestamp", "image_width", "image_height", "source_reference"]
ANNOTATION_FIELDS = ["sequence_id", "frame_id", "track_id", "class_id", "x1", "y1", "x2", "y2"]


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def manifest_rows(timestamps=(0.0, 0.1)):
    return [
        {"sequence_id": "seq", "frame_id": str(i + 1), "source_frame_index": str(i), "timestamp": str(t), "image_width": "100", "image_height": "80", "source_reference": "video.mp4"}
        for i, t in enumerate(timestamps)
    ]


def annotation_rows(rows):
    return [{"sequence_id": "seq", "frame_id": str(frame), "track_id": str(track), "class_id": str(cls), "x1": str(x1), "y1": str(y1), "x2": str(x2), "y2": str(y2)} for frame, track, cls, x1, y1, x2, y2 in rows]


def run_validation(tmp_path, manifests=None, annotations=None):
    manifest = tmp_path / "manifest.csv"
    labels = tmp_path / "labels.csv"
    write_csv(manifest, FIELDS, manifests if manifests is not None else manifest_rows())
    write_csv(labels, ANNOTATION_FIELDS, annotations if annotations is not None else [])
    return validate(manifest, labels)


def codes(report):
    return {item["code"] for item in report["errors"] + report["warnings"]}


def test_empty_identity_annotations_are_pending(tmp_path):
    report = run_validation(tmp_path)
    assert report["status"] == "DATA READY — IDENTITY ANNOTATION PENDING"
    assert report["identity_ground_truth"] == "pending"
    assert "identity_annotation_pending" in codes(report)


def test_duplicate_frame_id_is_rejected(tmp_path):
    rows = manifest_rows()
    rows[1]["frame_id"] = rows[0]["frame_id"]
    report = run_validation(tmp_path, manifests=rows)
    assert report["status"] == "FAIL"
    assert "duplicate_frame_id" in codes(report)


def test_non_increasing_timestamp_is_rejected(tmp_path):
    report = run_validation(tmp_path, manifests=manifest_rows((0.1, 0.1)))
    assert report["status"] == "FAIL"
    assert "timestamp_not_increasing" in codes(report)


def test_annotation_frame_must_exist(tmp_path):
    report = run_validation(tmp_path, annotations=annotation_rows([(3, 1, 0, 1, 1, 10, 10)]))
    assert report["status"] == "FAIL"
    assert "annotation_frame_missing" in codes(report)


def test_bbox_must_be_finite_and_in_bounds(tmp_path):
    report = run_validation(tmp_path, annotations=annotation_rows([(1, 1, 0, -1, 1, 101, 10)]))
    assert report["status"] == "FAIL"
    assert {"bbox_out_of_bounds"} <= codes(report)


def test_duplicate_track_in_frame_is_rejected(tmp_path):
    report = run_validation(tmp_path, annotations=annotation_rows([
        (1, 1, 0, 1, 1, 10, 10),
        (1, 1, 0, 2, 2, 11, 11),
    ]))
    assert report["status"] == "FAIL"
    assert "duplicate_track_in_frame" in codes(report)


def test_identity_rows_are_unverified_without_explicit_verification(tmp_path):
    report = run_validation(tmp_path, annotations=annotation_rows([(1, 1, 0, 1, 1, 10, 10)]))
    assert report["identity_ground_truth"] == "unverified"
    assert "identity_annotation_unverified" in codes(report)
