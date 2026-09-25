import json

from scripts.audit_split_leakage import audit


def test_audit_detects_cross_split_group_and_neighbor(tmp_path):
    manifest = tmp_path / "manifest.json"
    rows = [
        {"image": "/data/RGBT_test_20200101_120000_1_1_visible_10.jpg", "group": "base:RGBT_test_20200101_120000_1_1", "split": "train", "image_hash": "a"},
        {"image": "/data/RGBT_test_20200101_120000_1_1_visible_20.jpg", "group": "base:RGBT_test_20200101_120000_1_1", "split": "val", "image_hash": "b"},
    ]
    manifest.write_text(json.dumps({"samples": rows}), encoding="utf-8")
    result = audit(manifest)
    assert result["group_overlap_count"] == 1
    assert result["cross_split_neighbor_pairs"] == 1
    assert result["status"] == "CONFIRMED TEMPORAL LEAKAGE"


def test_audit_does_not_call_unique_frames_duplicate(tmp_path):
    manifest = tmp_path / "manifest.json"
    rows = [
        {"image": "/data/RGBT_test_20200101_120000_1_1_visible_10.jpg", "group": "base:RGBT_test_20200101_120000_1_1", "split": "train", "image_hash": "a"},
        {"image": "/data/RGBT_test_20200101_120000_1_1_visible_20.jpg", "group": "base:RGBT_test_20200101_120000_1_1", "split": "val", "image_hash": "b"},
    ]
    manifest.write_text(json.dumps({"samples": rows}), encoding="utf-8")
    result = audit(manifest)
    assert result["same_source_frame_cross_split_count"] == 0
    assert result["cross_split_provenance_collisions"]["image_hash"] == 0
