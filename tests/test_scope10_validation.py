import json
from pathlib import Path

from scripts.scope10_validation import validate_dataset_manifest, validate_sequence


def write_sequence(tmp_path: Path, sequence_id="seq_a", timestamps=(0.0, 1.0), boxes=((1, 1, 5, 5),)):
    root = tmp_path / sequence_id
    (root / "annotations").mkdir(parents=True)
    (root / "sequence.json").write_text(json.dumps({"sequence_id": sequence_id, "frame_count": len(timestamps)}), encoding="utf-8")
    lines = ["sequence_id,frame_id,source_frame_index,timestamp,image_width,image_height,source_reference,annotation_reference\n"]
    for index, timestamp in enumerate(timestamps):
        lines.append(f"{sequence_id},{index + 1},{index},{timestamp},640,512,video.mp4,labels.mat\n")
    (root / "frame_manifest.csv").write_text("".join(lines), encoding="utf-8")
    annotation_lines = ["sequence_id,frame_id,source_label,x1,y1,x2,y2,source_annotation_reference\n"]
    for index, box in enumerate(boxes, start=1):
        annotation_lines.append(f"{sequence_id},{index},DRONE,{box[0]},{box[1]},{box[2]},{box[3]},labels.mat\n")
    (root / "annotations/source_boxes.csv").write_text("".join(annotation_lines), encoding="utf-8")
    return root


def dataset_entry(sequence_id, source_member="video.mp4", status="UNVERIFIED", permission=("diagnostic_only",), identity="IDENTITY REVIEW REQUIRED"):
    return {
        "sequence_id": sequence_id,
        "source_archive": "archive.tar",
        "source_member": source_member,
        "source_member_sha256": f"hash-{source_member}",
        "frame_count": 2,
        "fps": 30.0,
        "resolution": [640, 512],
        "annotation_status": "SOURCE_BOXES_NORMALIZED",
        "identity_status": identity,
        "training_overlap_status": status,
        "permission": list(permission),
    }


def test_invalid_timestamp_is_rejected(tmp_path):
    root = write_sequence(tmp_path, timestamps=(1.0, 1.0))
    report = validate_sequence({"sequence_id": "seq_a", "frame_count": 2}, root)
    assert report["status"] == "FAIL"
    assert any(error["code"] == "timestamp_not_monotonic" for error in report["errors"])


def test_duplicate_sequence_id_and_same_video_are_distinguished(tmp_path):
    first = write_sequence(tmp_path, "seq_a")
    second = write_sequence(tmp_path, "seq_b")
    entries = [dataset_entry("seq_a"), dataset_entry("seq_a")]
    report = validate_dataset_manifest({"sequences": entries}, {"seq_a": first})
    assert any(error["code"] == "duplicate_sequence_id" for error in report["errors"])

    entries = [dataset_entry("seq_a"), dataset_entry("seq_b")]
    report = validate_dataset_manifest({"sequences": entries}, {"seq_a": first, "seq_b": second})
    assert any(error["code"] == "same_source_video_collision" for error in report["errors"])


def test_provenance_unknown_is_warning_and_cannot_grant_independent_permission(tmp_path):
    root = write_sequence(tmp_path)
    item = dataset_entry("seq_a", status="UNVERIFIED", permission=("diagnostic_only", "independent_validation"))
    report = validate_dataset_manifest({"sequences": [item]}, {"seq_a": root})
    assert report["status"] == "FAIL"
    assert any(error["code"] == "unverified_independent_permission" for error in report["errors"])
    assert any(warning["code"] == "provenance_unknown" for warning in report["warnings"])


def test_source_disjoint_requires_independent_permission_and_verified_identity_for_metrics(tmp_path):
    root = write_sequence(tmp_path)
    item = dataset_entry("seq_a", status="CONFIRMED_SOURCE_DISJOINT", permission=("independent_validation",), identity="IDENTITY VERIFIED")
    report = validate_dataset_manifest({"sequences": [item]}, {"seq_a": root})
    assert report["status"] == "PASS"


def test_exact_duplicate_leakage_is_separate_class(tmp_path):
    first = write_sequence(tmp_path, "seq_a")
    second = write_sequence(tmp_path, "seq_b")
    one = dataset_entry("seq_a")
    two = dataset_entry("seq_b", source_member="other.mp4")
    one["frame_hashes"] = ["same-frame-hash"]
    two["frame_hashes"] = ["same-frame-hash"]
    report = validate_dataset_manifest({"sequences": [one, two]}, {"seq_a": first, "seq_b": second})
    assert any(error["code"] == "exact_duplicate_leakage" for error in report["errors"])
    assert not any(error["code"] == "same_source_video_collision" for error in report["errors"])


def test_multi_object_annotation_is_aligned_and_valid(tmp_path):
    root = write_sequence(tmp_path, boxes=((1, 1, 5, 5),))
    path = root / "annotations/source_boxes.csv"
    path.write_text(path.read_text() + "seq_a,1,DRONE,10,10,20,20,labels.mat\n", encoding="utf-8")
    report = validate_sequence({"sequence_id": "seq_a", "frame_count": 2}, root)
    assert report["status"] == "PASS"
    assert report["annotation_rows"] == 2
