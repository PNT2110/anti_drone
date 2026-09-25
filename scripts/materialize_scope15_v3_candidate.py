"""Materialize the holdout-preserving Scope 15 V3 candidate.

This creates a new physical-copy dataset from the audited Scope 13 mapping.
It intentionally does not create data.yaml; that file is added only after the
independent direct-disk audit passes.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "data/processed/drone-single-class/manifest.json"
V2 = ROOT / "data/processed/drone-single-class-v2/manifest.json"
V2_REGISTRY = ROOT / "data/processed/drone-single-class-v2/split_registry.json"
V2_AUDIT = ROOT / "data/processed/drone-single-class-v2/audit.json"
S13_MAPPING = ROOT / ".runtime/scope13/rgbt_archive_mapping.csv"
S14_CSV = ROOT / ".runtime/scope14/v3_dry_run_b_conservative.csv"
S14_AUDIT = ROOT / ".runtime/scope14/v3_dry_run_audit.json"
OUTPUT = ROOT / "data/processed/drone-single-class-v3-candidate"
EXPECTED = {
    "v1_manifest": "3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d",
    "v2_manifest": "9605532a2b24566b691554125074c37f198c452bce343883b2a6720847299aa1",
    "v2_registry": "5819f6df78156561f3907e0eac05186dd5d77fe556699c74bad0ee5d40f51ed9",
    "v2_audit": "ab6a02db3b5efdff5f4c95d130ab4f9b06eddd18b9541aa7157ebb86f016a120",
    "scope13_mapping": "ffb0d14247ff02f9d30e14011769435fd296103e4fe735e02abbb30cd1396d4e",
    "scope14_csv": "eb045f9d0c9f6f247e092b3b8c45389d80a495c7a26e2f8523554dd89b6afa57",
    "scope14_audit": "cf20f29f4e1646b0e1b6ae62f538bae7785a0437bd9ed4afff0d72ff5ada168b",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def archive_partition(member: str) -> str:
    match = re.search(r"(?:^|/)Anti-UAV300/data/Anti-UAV300/(train|val|test)/", member)
    if match is None:
        raise RuntimeError(f"BLOCKED: cannot parse original source partition: {member}")
    return match.group(1)


def main() -> int:
    paths = {"v1_manifest": V1, "v2_manifest": V2, "v2_registry": V2_REGISTRY, "v2_audit": V2_AUDIT, "scope13_mapping": S13_MAPPING, "scope14_csv": S14_CSV, "scope14_audit": S14_AUDIT}
    observed = {key: sha256(path) for key, path in paths.items()}
    if observed != EXPECTED:
        raise RuntimeError(f"BLOCKED: Scope 15 input checksum mismatch: {observed}")
    if OUTPUT.exists():
        raise RuntimeError(f"BLOCKED: output exists; refusing to overwrite: {OUTPUT}")
    v1 = json.loads(V1.read_text(encoding="utf-8"))["samples"]
    v2 = json.loads(V2.read_text(encoding="utf-8"))["samples"]
    v2_audit = json.loads(V2_AUDIT.read_text(encoding="utf-8"))
    s14_audit = json.loads(S14_AUDIT.read_text(encoding="utf-8"))
    if v2_audit.get("status") != "PASS" or s14_audit["option_b_conservative"]["split_counts"] != {"train": 12142, "val": 8237, "test": 9848}:
        raise RuntimeError("BLOCKED: accepted V2/Scope 14 audit does not match expected conservative policy")
    v1_by_image = {(row["source"], row["image"]): (index, row) for index, row in enumerate(v1)}
    v2_by_image = {(row["source"], row["image"]): (index, row) for index, row in enumerate(v2)}
    mapping = list(csv.DictReader(S13_MAPPING.open(encoding="utf-8")))
    dry_rows = list(csv.DictReader(S14_CSV.open(encoding="utf-8")))
    if len(mapping) != 30227 or len(dry_rows) != 30227:
        raise RuntimeError("BLOCKED: Scope 13/14 row count mismatch")
    dry_by_image = {row["image"]: row for row in dry_rows}
    rows = []
    estimated_bytes = 0
    seen = set()
    for index, source_map in enumerate(mapping):
        key = ("base", source_map["image"])
        v1_index, v1_row = v1_by_image.get(key, (None, None))
        v2_index, v2_row = v2_by_image.get(key, (None, None))
        if v1_row is None or v2_row is None or v2_row.get("assignment_status") != "ASSIGNED":
            raise RuntimeError(f"BLOCKED: mapping row missing or not assigned: {source_map['image']}")
        dry = dry_by_image.get(source_map["image"])
        source_partition = archive_partition(source_map["source_video_member"])
        if dry is None or dry["split"] != source_partition or dry["original_source_split"] != source_partition:
            raise RuntimeError(f"BLOCKED: conservative split mismatch: {source_map['image']}")
        source_image = Path(v1_row["image"])
        source_label = Path(v1_row["label"]) if v1_row.get("label") else None
        if not source_image.is_file() or source_label is None or not source_label.is_file():
            raise RuntimeError(f"BLOCKED: missing source image/label: {source_image} / {source_label}")
        output_image_name = Path(v2_row["output_image"]).name
        output_label_name = Path(v2_row["output_label"]).stem + ".txt"
        output_key = (dry["split"], output_image_name, output_label_name)
        if output_key in seen:
            raise RuntimeError(f"BLOCKED: duplicate output key: {output_key}")
        seen.add(output_key)
        estimated_bytes += source_image.stat().st_size + source_label.stat().st_size
        rows.append({
            "sample_id": f"v3-candidate:{index:05d}",
            "v1_sample_reference": f"v1:{v1_index:05d}",
            "v2_sample_reference": f"v2:{v2_index:05d}",
            "source": "base",
            "source_image": str(source_image),
            "source_label": str(source_label),
            "image_hash": v2_row["image_hash"],
            "source_archive": "Anti-UAV300.tar",
            "source_video_member": source_map["source_video_member"],
            "source_annotation_member": source_map["source_annotation_member"],
            "source_sequence_directory": source_map["source_sequence_id"],
            "source_frame_index": int(source_map["source_frame_index"]),
            "modality": source_map["modality"],
            "candidate_prefix": source_map["source_session_prefix"],
            "original_source_partition": dry["original_source_split"],
            "candidate_split": dry["split"],
            "provenance_status": "CONFIRMED_SOURCE_SEQUENCE_ARCHIVE_MEMBER; SESSION_DISJOINT_UNVERIFIED",
            "output_image_name": output_image_name,
            "output_label_name": output_label_name,
            "assignment_status": "ASSIGNED",
            "v1_split": v1_row.get("split"),
        })
    free_bytes = shutil.disk_usage(OUTPUT.parent).free
    safety_required = int(estimated_bytes * 1.10) + 256 * 1024 * 1024
    if free_bytes < safety_required:
        raise RuntimeError(f"BLOCKED: insufficient free space: free={free_bytes}, required={safety_required}")
    temp = OUTPUT.with_name(OUTPUT.name + f".building-{os.getpid()}")
    if temp.exists():
        raise RuntimeError(f"BLOCKED: stale temporary directory exists: {temp}")
    started = time.time()
    try:
        for split in ("train", "val", "test"):
            (temp / "images" / split).mkdir(parents=True, exist_ok=True)
            (temp / "labels" / split).mkdir(parents=True, exist_ok=True)
        materialized = []
        for position, row in enumerate(rows, 1):
            image_dst = temp / "images" / row["candidate_split"] / row["output_image_name"]
            label_dst = temp / "labels" / row["candidate_split"] / row["output_label_name"]
            shutil.copy2(row["source_image"], image_dst)
            shutil.copy2(row["source_label"], label_dst)
            if image_dst.is_symlink() or label_dst.is_symlink():
                raise RuntimeError("BLOCKED: symlink materialization detected")
            source_hash = sha256(Path(row["source_image"]))
            output_hash = sha256(image_dst)
            if source_hash != row["image_hash"] or output_hash != source_hash:
                raise RuntimeError(f"BLOCKED: image hash mismatch: {row['source_image']}")
            materialized.append(row | {
                "output_image": str(image_dst.relative_to(temp)),
                "output_label": str(label_dst.relative_to(temp)),
                "output_image_sha256": output_hash,
                "source_label_sha256": sha256(Path(row["source_label"])),
                "output_label_sha256": sha256(label_dst),
            })
            if position % 2000 == 0:
                print(f"copied {position}/{len(rows)}", flush=True)
        metadata = {
            "dataset_id": "drone-single-class-v3-candidate",
            "dataset_version": "scope15-holdout-preserving-candidate-v1",
            "source_v1_manifest_sha256": observed["v1_manifest"],
            "source_v2_manifest_sha256": observed["v2_manifest"],
            "source_v2_registry_sha256": observed["v2_registry"],
            "source_v2_audit_sha256": observed["v2_audit"],
            "scope13_mapping_sha256": observed["scope13_mapping"],
            "scope14_conservative_dry_run_sha256": observed["scope14_csv"],
            "seed": 42,
            "candidate_group_rule": "original_source_partition + whole Anti-UAV300 source sequence + whole date/time prefix",
            "assigned_sample_count": len(materialized),
            "quarantine_sample_count_excluded": 6505,
            "quarantine_group_count_excluded": 4172,
            "session_disjoint": "UNVERIFIED",
            "materialization": "physical copy2; no symlink/hardlink; no resize or label rewrite",
            "created_at_unix": started,
        }
        write_json(temp / "manifest.json", {"metadata": metadata, "samples": materialized})
        candidate_manifest_sha256 = sha256(temp / "manifest.json")
        write_json(temp / "split_registry.json", {"dataset_id": metadata["dataset_id"], "candidate_manifest_sha256": candidate_manifest_sha256, "source_v2_manifest_sha256": observed["v2_manifest"], "seed": 42, "actual_counts": dict(Counter(row["candidate_split"] for row in materialized)), "sample_count": len(materialized), "source_sequence_overlap": 0, "candidate_prefix_overlap": 0, "session_disjoint": "UNVERIFIED", "production_status": "CANDIDATE_ONLY"})
        write_json(temp / "training_provenance.json", {"dataset_manifest_sha256": candidate_manifest_sha256, "source_v2_manifest_sha256": observed["v2_manifest"], "scope13_mapping_sha256": observed["scope13_mapping"], "scope14_policy_sha256": observed["scope14_audit"], "seed": 42, "sample_ids": [row["sample_id"] for row in materialized], "source_references": ["v1_sample_reference", "v2_sample_reference", "source_archive", "source_video_member", "source_sequence_directory", "source_frame_index", "modality", "candidate_prefix"], "excluded_quarantine": {"samples": 6505, "groups": 4172}, "validation_policy": "V3 val only for checkpoint/parameter selection; V3 test locked until decisions freeze", "resume_policy": "resume only from last.pt belonging to the same model/size run", "checkpoint_v1": "SPLIT_UNVERIFIED; not re-evaluated as independent"})
        write_json(temp / "materialization_report.json", {"status": "PASS", "sample_count": len(materialized), "split_counts": dict(Counter(row["candidate_split"] for row in materialized)), "estimated_source_bytes": estimated_bytes, "free_bytes_before": free_bytes, "safety_required_bytes": safety_required, "elapsed_seconds": time.time() - started, "data_yaml_created": False})
        os.replace(temp, OUTPUT)
    except Exception:
        raise
    print(json.dumps({"output": str(OUTPUT), "split_counts": dict(Counter(row["candidate_split"] for row in rows)), "quarantine_excluded": 6505}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
