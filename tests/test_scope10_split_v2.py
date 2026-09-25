import hashlib
import json
from pathlib import Path

from scripts.audit_group_disjoint_split_v2 import audit
from scripts.build_group_disjoint_split_v2 import build_manifest, classify_sample


ROOT = Path(__file__).resolve().parents[1]


def test_rgbt_sequence_frames_share_one_provenance_group():
    visible = {"source": "base", "group": "base:RGBT_train_20200101_120000_1_1", "image": "visible_001.jpg"}
    infrared = {"source": "base", "group": "base:RGBT_train_20200101_120000_1_1", "image": "infrared_001.jpg"}
    other_video = {"source": "base", "group": "base:RGBT_train_20200101_120000_1_2", "image": "visible_002.jpg"}
    assert classify_sample(visible) == "VERIFIED_SEQUENCE_GROUP"
    assert classify_sample(infrared) == "VERIFIED_SEQUENCE_GROUP"
    assert visible["group"] == infrared["group"]
    assert visible["group"] != other_video["group"]


def test_unknown_filename_provenance_is_quarantinable_not_independent():
    assert classify_sample({"source": "base", "group": "base:DUT_0001", "image": "x.jpg"}) == "GROUP_UNVERIFIED"
    assert classify_sample({"source": "my_dataset", "group": "my_dataset", "image": "x.jpg"}) == "GROUP_UNVERIFIED"


def test_seed_reproduces_v2_assignment_and_v1_is_untouched(tmp_path):
    v1 = ROOT / "data/processed/drone-single-class"
    before = {name: hashlib.sha256((v1 / name).read_bytes()).hexdigest() for name in ("manifest.json", "split_registry.json", "audit.json", "data.yaml")}
    output_a = tmp_path / "a"
    output_b = tmp_path / "b"
    build_manifest(v1 / "manifest.json", output_a, 42)
    build_manifest(v1 / "manifest.json", output_b, 42)
    for name in ("manifest.json", "split_registry.json"):
        assert hashlib.sha256((output_a / name).read_bytes()).hexdigest() == hashlib.sha256((output_b / name).read_bytes()).hexdigest()
    after = {name: hashlib.sha256((v1 / name).read_bytes()).hexdigest() for name in before}
    assert before == after


def test_audit_detects_sample_loss_and_duplicate(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = {
        "metadata": {},
        "samples": [
            {"source": "base", "image": "a.jpg", "image_hash": "a", "group": "base:RGBT_a", "split": "train"},
            {"source": "base", "image": "b.jpg", "image_hash": "b", "group": "base:RGBT_a", "split": "val"},
        ],
    }
    (source_dir / "manifest.json").write_text(json.dumps(source), encoding="utf-8")
    (source_dir / "split_registry.json").write_text("{}", encoding="utf-8")
    (source_dir / "audit.json").write_text("{}", encoding="utf-8")
    output = tmp_path / "v2"
    build_manifest(source_dir / "manifest.json", output, 42)
    doc = json.loads((output / "manifest.json").read_text())
    doc["samples"].pop()
    doc["samples"].append(dict(doc["samples"][0]))
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(doc), encoding="utf-8")
    report = audit(source_dir / "manifest.json", broken)
    assert report["status"] == "FAIL"
    assert any(error["code"] in {"sample_count_mismatch", "sample_duplicate", "sample_loss_or_extra"} for error in report["errors"])


def test_audit_detects_verified_group_split(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    samples = [
        {"source": "base", "image": "a.jpg", "image_hash": "a", "group": "base:RGBT_a", "split": "train"},
        {"source": "base", "image": "b.jpg", "image_hash": "b", "group": "base:RGBT_a", "split": "train"},
    ]
    (source_dir / "manifest.json").write_text(json.dumps({"metadata": {}, "samples": samples}), encoding="utf-8")
    (source_dir / "split_registry.json").write_text("{}", encoding="utf-8")
    (source_dir / "audit.json").write_text("{}", encoding="utf-8")
    output = tmp_path / "v2"
    build_manifest(source_dir / "manifest.json", output, 42)
    broken = json.loads((output / "manifest.json").read_text())
    broken["samples"][0]["split"] = "train"
    broken["samples"][1]["split"] = "val"
    broken_path = tmp_path / "broken.json"
    broken_path.write_text(json.dumps(broken), encoding="utf-8")
    report = audit(source_dir / "manifest.json", broken_path)
    assert any(error["code"] == "verified_group_split" for error in report["errors"])


def test_audit_reports_unverified_samples_as_quarantine_warning(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    samples = [{"source": "my_dataset", "image": "a.jpg", "image_hash": "a", "group": "my_dataset", "split": "train"}]
    (source_dir / "manifest.json").write_text(json.dumps({"metadata": {}, "samples": samples}), encoding="utf-8")
    (source_dir / "split_registry.json").write_text("{}", encoding="utf-8")
    (source_dir / "audit.json").write_text("{}", encoding="utf-8")
    output = tmp_path / "v2"
    build_manifest(source_dir / "manifest.json", output, 42)
    report = audit(source_dir / "manifest.json", output / "manifest.json")
    assert report["status"] == "PASS"
    assert report["quarantined_sample_count"] == 1
    assert report["independent_validation_claim"] is False
    assert report["warnings"][0]["code"] == "provenance_unknown"
