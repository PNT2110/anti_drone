import csv

from scripts.prepare_identity_review import EVIDENCE_FIELDS, REVIEW_FIELDS, prepare
from scripts.validate_identity_review import validate_review


SOURCE_FIELDS = ["sequence_id", "frame_id", "source_label", "x1", "y1", "x2", "y2", "source_annotation_reference"]
MANIFEST_FIELDS = ["sequence_id", "frame_id", "source_frame_index", "timestamp", "image_width", "image_height", "source_reference"]


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def make_artifacts(tmp_path, count=2):
    manifest = tmp_path / "manifest.csv"
    source = tmp_path / "source_boxes.csv"
    write_csv(manifest, MANIFEST_FIELDS, [
        {"sequence_id": "seq", "frame_id": str(i), "source_frame_index": str(i - 1), "timestamp": str((i - 1) / 30), "image_width": "640", "image_height": "512", "source_reference": "video.mp4"}
        for i in range(1, count + 1)
    ])
    write_csv(source, SOURCE_FIELDS, [
        {"sequence_id": "seq", "frame_id": str(i), "source_label": "DRONE", "x1": "1", "y1": "2", "x2": "11", "y2": "12", "source_annotation_reference": f"sidecar:row={i - 1}"}
        for i in range(1, count + 1)
    ])
    return manifest, source


def test_review_manifest_defaults_to_pending(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    summary = prepare(source, manifest, review)
    assert summary["status"] == "HUMAN REVIEW PENDING"
    rows = list(csv.DictReader(review.open(encoding="utf-8")))
    assert len(rows) == 2
    assert set(rows[0]) == set(REVIEW_FIELDS)
    assert all(row["review_status"] == "PENDING" and row["candidate_identity"] == "" for row in rows)


def test_pending_review_blocks_ground_truth_export(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    gt = tmp_path / "ground_truth.csv"
    report = validate_review(review, source, gt, export_ground_truth=True)
    assert report["status"] == "IDENTITY ANNOTATION PENDING"
    assert report["ground_truth_exported"] is False
    assert report["counts"]["pending_frames"] == 2
    assert not gt.exists()


def test_partial_review_is_not_verified(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    rows = list(csv.DictReader(review.open(encoding="utf-8")))
    rows[0]["review_status"] = "VERIFIED"
    rows[0]["candidate_identity"] = "1"
    rows[0]["review_note"] = "Continuous visual identity confirmed."
    write_csv(review, REVIEW_FIELDS, rows)
    report = validate_review(review, source, tmp_path / "ground_truth.csv")
    assert report["status"] == "IDENTITY ANNOTATION PENDING"
    assert report["counts"]["verified_frames"] == 1
    assert report["counts"]["pending_frames"] == 1


def test_duplicate_review_frame_fails(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    rows = list(csv.DictReader(review.open(encoding="utf-8")))
    rows[1]["frame_id"] = rows[0]["frame_id"]
    write_csv(review, REVIEW_FIELDS, rows)
    report = validate_review(review, source, tmp_path / "ground_truth.csv")
    assert report["status"] == "FAIL"
    assert any(item["code"] == "duplicate_review_frame" for item in report["errors"])


def test_missing_source_annotation_fails(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    source_rows = list(csv.DictReader(source.open(encoding="utf-8")))
    write_csv(source, SOURCE_FIELDS, source_rows[:1])
    report = validate_review(review, source, tmp_path / "ground_truth.csv")
    assert report["status"] == "FAIL"
    assert any(item["code"] == "missing_source_annotation" for item in report["errors"])


def test_complete_review_can_export_provenanced_ground_truth(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    rows = list(csv.DictReader(review.open(encoding="utf-8")))
    for row in rows:
        row.update({"candidate_identity": "1", "review_status": "VERIFIED", "review_note": "Human visual review complete."})
    write_csv(review, REVIEW_FIELDS, rows)
    gt = tmp_path / "ground_truth.csv"
    report = validate_review(review, source, gt, export_ground_truth=True)
    assert report["status"] == "PASS"
    assert report["ground_truth_exported"] is True
    gt_rows = list(csv.DictReader(gt.open(encoding="utf-8")))
    assert len(gt_rows) == 2
    assert gt_rows[0]["track_id"] == "1"
    assert report["provenance"]["identity_status"] == "VERIFIED"


def evidence_row(status="VERIFIED", track_id="1", start=1, end=2, note="Continuous identity confirmed."):
    return {
        "sequence_id": "seq",
        "frame_start": str(start),
        "frame_end": str(end),
        "assigned_track_id": track_id,
        "review_status": status,
        "review_note": note,
        "review_timestamp": "2026-09-22T12:00:00+07:00",
        "reviewer_reference": "human-reviewer-01",
    }


def test_valid_batch_evidence_can_export_ground_truth(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    evidence = tmp_path / "evidence.csv"
    write_csv(evidence, EVIDENCE_FIELDS, [evidence_row()])
    gt = tmp_path / "ground_truth.csv"
    report = validate_review(review, source, gt, evidence_path=evidence, export_ground_truth=True)
    assert report["status"] == "PASS"
    assert report["ground_truth_exported"] is True
    assert report["evidence_summary"]["covered_frames"] == 2
    assert report["provenance"]["evidence_sha256"]


def test_overlapping_batch_evidence_fails(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    evidence = tmp_path / "evidence.csv"
    write_csv(evidence, EVIDENCE_FIELDS, [evidence_row(start=1, end=2), evidence_row(start=2, end=2)])
    report = validate_review(review, source, tmp_path / "ground_truth.csv", evidence_path=evidence)
    assert report["status"] == "FAIL"
    assert any(item["code"] == "overlapping_evidence_segment" for item in report["errors"])


def test_out_of_range_batch_evidence_fails(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    evidence = tmp_path / "evidence.csv"
    write_csv(evidence, EVIDENCE_FIELDS, [evidence_row(start=1, end=3)])
    report = validate_review(review, source, tmp_path / "ground_truth.csv", evidence_path=evidence)
    assert report["status"] == "FAIL"
    assert any(item["code"] == "evidence_out_of_range" for item in report["errors"])


def test_invalid_batch_identity_and_missing_reviewer_evidence_fail(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    evidence = tmp_path / "evidence.csv"
    row = evidence_row(track_id="not-an-id")
    row["reviewer_reference"] = ""
    write_csv(evidence, EVIDENCE_FIELDS, [row])
    report = validate_review(review, source, tmp_path / "ground_truth.csv", evidence_path=evidence)
    codes = {item["code"] for item in report["errors"]}
    assert report["status"] == "FAIL"
    assert "verified_assigned_track_id_missing" in codes
    assert "reviewer_evidence_missing" in codes


def test_partial_batch_evidence_remains_pending_without_export(tmp_path):
    manifest, source = make_artifacts(tmp_path, count=3)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    evidence = tmp_path / "evidence.csv"
    write_csv(evidence, EVIDENCE_FIELDS, [evidence_row(start=1, end=2)])
    gt = tmp_path / "ground_truth.csv"
    report = validate_review(review, source, gt, evidence_path=evidence)
    assert report["status"] == "IDENTITY ANNOTATION PENDING"
    assert report["counts"]["verified_frames"] == 2
    assert report["counts"]["pending_frames"] == 1
    assert report["ground_truth_exported"] is False
    assert not gt.exists()


def test_unverified_batch_evidence_is_not_official_ground_truth(tmp_path):
    manifest, source = make_artifacts(tmp_path)
    review = tmp_path / "review.csv"
    prepare(source, manifest, review)
    evidence = tmp_path / "evidence.csv"
    write_csv(evidence, EVIDENCE_FIELDS, [evidence_row(status="NEEDS_REVIEW", track_id="")])
    report = validate_review(review, source, tmp_path / "ground_truth.csv", evidence_path=evidence)
    assert report["status"] == "IDENTITY ANNOTATION PENDING"
    assert report["counts"]["needs_review_frames"] == 2
    assert report["counts"]["verified_frames"] == 0
