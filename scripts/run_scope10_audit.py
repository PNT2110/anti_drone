#!/usr/bin/env python3
"""Audit source provenance and build the Scope 10 temporal validation manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.scope10_validation import sha256, validate_dataset_manifest


ARCHIVE_DIR = ROOT / "data/import_data_rar"
PROCESSED = ROOT / "data/processed/drone-single-class"
TRACKING = ROOT / "data/tracking_eval"
RUNTIME = ROOT / ".runtime/scope10"


def member_sha256(archive: Path, member_name: str) -> str:
    digest = hashlib.sha256()
    with tarfile.open(archive) as handle:
        source = handle.extractfile(member_name)
        if source is None:
            raise FileNotFoundError(member_name)
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def apparent_sequence_id(path: str) -> str | None:
    stem = Path(path).stem
    match = re.search(r"(?i)(?:V|IR)_[A-Z]+_\d+$", stem)
    if match:
        return match.group(0)
    parts = path.split("/")
    for part in parts:
        if re.fullmatch(r"(?i)(?:video|sequence)[_-]?\d+", part):
            return part
    if len(parts) >= 2 and re.fullmatch(r"\d{8}_[0-9_]+", parts[-2]):
        return parts[-2]
    return None


def inventory_archive(path: Path, recorded: dict[str, Any]) -> dict[str, Any]:
    with tarfile.open(path) as handle:
        members = handle.getmembers()
    names = [member.name for member in members]
    files = [member for member in members if member.isfile()]
    video = [member.name for member in files if Path(member.name).suffix.lower() in {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpg", ".mpeg"}]
    annotation = [member.name for member in files if Path(member.name).suffix.lower() in {".mat", ".json", ".xml", ".txt", ".csv", ".jsonl"} or re.search(r"label|annotation|ground.?truth|gt", member.name, re.I)]
    sequence_ids = sorted({value for value in (apparent_sequence_id(name) for name in names) if value})
    modalities = sorted({token for token in ("visible", "infrared", "thermal", "rgb", "ir", "v") for name in names if re.search(rf"(?i)(?:^|[/_]){token}(?:[/_.]|$)", name)})
    formats = Counter(Path(member.name).suffix.lower() or "<no_extension>" for member in files)
    return {
        "archive_name": path.name,
        "archive_path": str(path.relative_to(ROOT)),
        "size_bytes": path.stat().st_size,
        "archive_sha256": recorded.get("sha256"),
        "archive_sha256_source": "existing manifest/audit inventory; not recomputed in Scope 10" if recorded.get("sha256") else "not_available",
        "member_count": len(members),
        "file_member_count": len(files),
        "video_member_count": len(video),
        "video_members_sample": video[:20],
        "annotation_member_count": len(annotation),
        "annotation_members_sample": annotation[:20],
        "apparent_sequence_id_count": len(sequence_ids),
        "apparent_sequence_ids_sample": sequence_ids[:40],
        "modalities": modalities,
        "member_extension_counts": dict(sorted(formats.items())),
        "nested_archives": [name for name in names if Path(name).suffix.lower() in {".zip", ".tar", ".xz", ".gz"}],
        "listing_status": "PASS",
    }


def source_inventory(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    recorded = {item["name"]: item for item in manifest["metadata"]["source_inventory"]}
    results = []
    for item in sorted(recorded.values(), key=lambda value: value["name"]):
        path = ROOT / item["path"]
        if path.suffix.lower() not in {".tar", ".xz", ".zip", ".tgz"}:
            continue
        results.append(inventory_archive(path, item))
    return results


def source_training_map(manifest: dict[str, Any], checkpoint: Path, model_provenance: Path, selection_provenance: Path) -> dict[str, Any]:
    source_counts = Counter(row.get("source") for row in manifest["samples"])
    archive_rows = []
    for item in manifest["metadata"]["source_inventory"]:
        name = item["name"]
        if not name.endswith((".tar", ".tar.xz")):
            continue
        if name == "my_dataset.tar.xz":
            classification = "CONFIRMED TRAIN SOURCE"
            evidence = ["processed manifest metadata names my_dataset archive", f"{source_counts['my_dataset']} manifest samples have source=my_dataset", "metadata marks archive eligible_for_training=true"]
        else:
            classification = "UNVERIFIED"
            evidence = ["archive is present in the processed source inventory", "checkpoint provenance points to the processed manifest, not archive members", "no durable archive/member/video key maps this archive to or away from training rows"]
        archive_rows.append({"archive_name": name, "classification": classification, "evidence": evidence, "archive_sha256": item.get("sha256"), "eligible_for_training": item.get("eligible_for_training")})
    return {
        "status": "PASS",
        "classification_definitions": {
            "CONFIRMED TRAIN SOURCE": "direct training-manifest/source evidence",
            "CONFIRMED SOURCE-DISJOINT": "durable evidence that source is absent from checkpoint training input",
            "UNVERIFIED": "insufficient archive/member mapping; no inference from filename absence",
        },
        "archive_classification": archive_rows,
        "training_source_counts": dict(source_counts),
        "checkpoint_provenance": {
            "checkpoint": str(checkpoint.relative_to(ROOT)),
            "checkpoint_sha256_actual": sha256(checkpoint),
            "model_training_provenance": json.loads(model_provenance.read_text(encoding="utf-8")),
            "selection_provenance": json.loads(selection_provenance.read_text(encoding="utf-8")),
            "dataset_manifest_sha256_actual": sha256(PROCESSED / "manifest.json"),
            "split_registry_sha256_actual": sha256(PROCESSED / "split_registry.json"),
        },
        "conclusion": "No archive other than my_dataset is proven as a training source, and no archive is proven source-disjoint from the checkpoint. Halmstad remains UNVERIFIED.",
    }


def sequence_entry(sequence_dir: Path, archive: Path, archive_sha: str | None) -> dict[str, Any]:
    sequence = json.loads((sequence_dir / "sequence.json").read_text(encoding="utf-8"))
    source_member = sequence.get("source_member") or sequence.get("video_member")
    source_hash = sequence.get("source_member_sha256")
    identity = sequence.get("identity_status")
    if sequence["sequence_id"] == "halmstad_v_drone_001":
        identity = "IDENTITY VERIFIED"
        training_status = "UNVERIFIED"
        permission = ["diagnostic_only"]
        annotation_status = "USER_VERIFIED_GROUND_TRUTH"
        evidence = ["Scope 06 user review and official GT validator PASS", "Scope 05 archive-to-training mapping remains unresolved"]
    else:
        training_status = "UNVERIFIED"
        permission = ["diagnostic_only"]
        annotation_status = sequence.get("annotation_status", "SOURCE_BOXES_NORMALIZED")
        evidence = ["Halmstad archive member is unique within the inventory", "checkpoint training manifest has no archive-member/video provenance key", "source-disjointness therefore cannot be claimed"]
    return {
        "sequence_id": sequence["sequence_id"],
        "source_archive": sequence.get("source_archive") or sequence.get("archive") or str(archive.relative_to(ROOT)),
        "source_member": source_member,
        "source_hash_or_reference": source_hash or "member hash not recorded in prior Scope 03 artifact",
        "source_member_sha256": source_hash,
        "frame_count": int(sequence["frame_count"]),
        "fps": float(sequence["fps"]),
        "resolution": sequence.get("resolution") or [int(sequence["width"]), int(sequence["height"])],
        "annotation_status": annotation_status,
        "identity_status": identity,
        "training_overlap_status": training_status,
        "selection_status": "REFERENCE_DIAGNOSTIC_ONLY" if sequence["sequence_id"] == "halmstad_v_drone_001" else "PROVENANCE_UNVERIFIED",
        "provenance_evidence": evidence,
        "permission": permission,
        "sequence_directory": str(sequence_dir.relative_to(ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=RUNTIME)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    processed_manifest = json.loads((PROCESSED / "manifest.json").read_text(encoding="utf-8"))
    inventory = source_inventory(processed_manifest)
    (args.output_dir / "source_archive_inventory.json").write_text(json.dumps({"status": "PASS", "archives": inventory}, indent=2) + "\n", encoding="utf-8")
    map_report = source_training_map(
        processed_manifest,
        ROOT / "artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2/weights/best.pt",
        ROOT / "artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2/anti_drone_provenance.json",
        ROOT / "artifacts/benchmarks/model-selection/yolov8n/provenance.json",
    )
    (args.output_dir / "training_source_map.json").write_text(json.dumps(map_report, indent=2) + "\n", encoding="utf-8")
    archive = ROOT / "data/import_data_rar/Halmstad-Drone.tar"
    sequence_dirs = {"halmstad_v_drone_001": TRACKING / "sequence_001"}
    sequence_dirs.update({f"halmstad_v_drone_{number}": TRACKING / directory for number, directory in (("046", "sequence_002"), ("048", "sequence_003"), ("045", "sequence_004"))})
    entries = [sequence_entry(path, archive, None) for path in sequence_dirs.values()]
    dataset = {
        "manifest_version": "scope10-v1",
        "status": "VALIDATION_SET_READY_PROVENANCE_UNVERIFIED",
        "dataset_scope": "temporal validation preparation; no tracker benchmark",
        "source_archive_inventory": str((args.output_dir / "source_archive_inventory.json").relative_to(ROOT)),
        "training_source_map": str((args.output_dir / "training_source_map.json").relative_to(ROOT)),
        "sequence_count": len(entries),
        "sequences": entries,
        "permission_policy": {
            "diagnostic_only": "allowed for any validated sequence with provenance uncertainty",
            "independent_validation": "allowed only when training_overlap_status=CONFIRMED_SOURCE_DISJOINT",
            "identity_metric_ready": "allowed only when identity_status=IDENTITY VERIFIED",
        },
        "split_status": "SPLIT_UNVERIFIED",
    }
    dataset_path = ROOT / "data/tracking_eval/temporal_validation_manifest.json"
    dataset_path.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")
    validation = validate_dataset_manifest(dataset, sequence_dirs)
    validation["manifest_sha256"] = sha256(dataset_path)
    (args.output_dir / "temporal_validation_audit.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    detector_status = {
        "status": "BLOCKED",
        "reason": "detector cache preparation requires the existing runtime's OpenCV path; cv2 is unavailable in this host",
        "checkpoint": str((ROOT / "artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2/weights/best.pt").relative_to(ROOT)),
        "checkpoint_sha256": sha256(ROOT / "artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2/weights/best.pt"),
        "no_cache_generated": True,
        "no_tracker_run": True,
    }
    (args.output_dir / "detector_cache_status.json").write_text(json.dumps(detector_status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS" if validation["status"] == "PASS" else "FAIL", "validation": validation, "detector_cache": detector_status}, indent=2))
    return 0 if validation["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
