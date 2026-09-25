"""Scope 11: conservative provenance audit for V2 quarantined samples.

This script only reads the accepted V1/V2 artifacts and source archives.  It
does not extract archives, alter manifests, or change split assignments.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from scripts.scope11_provenance import classify_match, group_aliases
except ModuleNotFoundError:  # direct ``python scripts/...py`` invocation
    from scope11_provenance import classify_match, group_aliases


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope11"
V1_PATH = ROOT / "data/processed/drone-single-class/manifest.json"
V2_DIR = ROOT / "data/processed/drone-single-class-v2"
V2_PATH = V2_DIR / "manifest.json"
REGISTRY_PATH = V2_DIR / "split_registry.json"
AUDIT_PATH = V2_DIR / "audit.json"
DUT_ARCHIVE = ROOT / "data/import_data_rar/DUT-Anti-UAV.tar"
MY_ARCHIVE = ROOT / "data/import_data_rar/my_dataset.tar.xz"

EXPECTED = {
    "v1_manifest": "3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d",
    "v2_manifest": "9605532a2b24566b691554125074c37f198c452bce343883b2a6720847299aa1",
    "v2_registry": "5819f6df78156561f3907e0eac05186dd5d77fe556699c74bad0ee5d40f51ed9",
    "v2_audit": "ab6a02db3b5efdff5f4c95d130ab4f9b06eddd18b9541aa7157ebb86f016a120",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_member(handle: tarfile.TarFile, member: tarfile.TarInfo) -> str:
    digest = hashlib.sha256()
    stream = handle.extractfile(member)
    if stream is None:
        return ""
    with stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def input_audit() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    v1 = json.loads(V1_PATH.read_text())
    v2 = json.loads(V2_PATH.read_text())
    registry = json.loads(REGISTRY_PATH.read_text())
    audit = json.loads(AUDIT_PATH.read_text())
    hashes = {
        "v1_manifest": sha256_file(V1_PATH),
        "v2_manifest": sha256_file(V2_PATH),
        "v2_registry": sha256_file(REGISTRY_PATH),
        "v2_audit": sha256_file(AUDIT_PATH),
    }
    quarantine = [row for row in v2["samples"] if row.get("assignment_status") == "QUARANTINED"]
    checks = {
        "hashes_match_expected": hashes == EXPECTED,
        "v1_sample_count": len(v1["samples"]),
        "v2_sample_count": len(v2["samples"]),
        "quarantine_sample_count": len(quarantine),
        "quarantine_group_count": len({row["group"] for row in quarantine}),
        "quarantine_source_counts": dict(Counter(row["source"] for row in quarantine)),
        "v2_audit_status": audit.get("status"),
        "v2_audit_independent_validation_claim": audit.get("independent_validation_claim"),
        "registry_sample_count": registry.get("sample_count"),
        "registry_quarantined_sample_count": registry.get("quarantined_sample_count"),
        "registry_group_unverified_count": registry.get("group_unverified_count"),
    }
    payload = {"expected_hashes": EXPECTED, "observed_hashes": hashes, "checks": checks}
    dump_json(RUNTIME / "input_audit.json", payload)
    if not checks["hashes_match_expected"] or checks["v2_audit_status"] != "PASS":
        raise RuntimeError("Scope 11 input audit blocked: accepted baseline does not match")
    if len(v1["samples"]) != 36732 or len(v2["samples"]) != 36732 or len(quarantine) != 6505:
        raise RuntimeError("Scope 11 input audit blocked: unexpected sample totals")
    return payload, v1["samples"], quarantine


def member_map(handle: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    return {member.name: member for member in handle.getmembers() if member.isfile()}


def base_record(row: dict[str, Any], v1_by_key: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    original = v1_by_key.get((row.get("source", ""), row.get("image", "")), {})
    return {
        "source": row.get("source", ""),
        "image": row.get("image", ""),
        "image_basename": Path(row.get("image", "")).name,
        "image_hash": row.get("image_hash", ""),
        "v2_group": row.get("group", ""),
        "v1_split": original.get("split", ""),
        "v1_group": original.get("group", ""),
        "provenance_status": "UNRESOLVED",
        "source_archive": "",
        "source_member": "",
        "source_video_or_session": "",
        "source_frame_index": "",
        "modality": "",
        "annotation_member": "",
        "evidence": "",
        "detection_member": "",
        "detection_hash": "",
        "exact_archive_hash_match": False,
        "tracking_match_count": 0,
        "tracking_exact_member_matches": "",
        "candidate_tracking_member_count": 0,
        "source_sequence_key": "",
        "checkpoint_sample_status": "",
    }


def audit_archive_members(rows: list[dict[str, Any]], v1_by_key: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    records = [base_record(row, v1_by_key) for row in rows]
    by_source = defaultdict(list)
    for record in records:
        by_source[record["source"]].append(record)

    my_rows = by_source.get("my_dataset", [])
    if my_rows:
        with tarfile.open(MY_ARCHIVE, "r:*") as archive:
            members = member_map(archive)
            wanted = {f"my_dataset/{record['image_basename']}" for record in my_rows}
            hash_cache: dict[str, str] = {}
            # The xz archive is expensive to seek in.  Hash requested members
            # in archive order, never by repeated random seeks.
            with tarfile.open(MY_ARCHIVE, "r:*") as stream:
                for member in stream:
                    if member.isfile() and member.name in wanted:
                        hash_cache[member.name] = sha256_member(stream, member)
            for record in my_rows:
                stem = Path(record["image_basename"]).stem
                image_name = f"my_dataset/{record['image_basename']}"
                label_name = f"my_dataset/{stem}.txt"
                record["source_archive"] = str(MY_ARCHIVE.relative_to(ROOT))
                record["source_member"] = image_name if image_name in members else ""
                record["annotation_member"] = label_name if label_name in members else ""
                if image_name in members:
                    record["exact_archive_hash_match"] = hash_cache[image_name] == record["image_hash"]
                # Flat image/label archive has no source sequence/session metadata.
                record["modality"] = "unknown"
                record["evidence"] = "exact_archive_member_and_hash; flat_archive_no_sequence_metadata"
                record["provenance_status"] = classify_match(
                    exact_archive_member=record["exact_archive_hash_match"], exact_tracking_members=[]
                )

    dut_rows = by_source.get("base", [])
    if dut_rows:
        with tarfile.open(DUT_ARCHIVE, "r:*") as archive:
            members = member_map(archive)
            hash_cache: dict[str, str] = {}
            tracking_by_stem: dict[str, list[str]] = defaultdict(list)
            tracking_re = re.compile(r"^DUT-Anti-UAV/tracking/data/Anti-UAV-Tracking-V0/(video\d+)/([^/]+\.jpg)$")
            for name in members:
                match = tracking_re.match(name)
                if match:
                    tracking_by_stem[Path(match.group(2)).stem].append(name)
            target_names = {
                name for name in members
                if name.startswith("DUT-Anti-UAV/detection/data/")
                and "/img/" in name
            }
            # Hash every tracking JPG once so a source frame can be recovered
            # even when the prepared detection basename is not the tracking
            # frame index.  Filename equality remains only a candidate clue.
            target_names.update(name for names in tracking_by_stem.values() for name in names)
            # Hash in tar order.  This avoids the repeated seek overhead of
            # extractfile() against a large archive.
            with tarfile.open(DUT_ARCHIVE, "r:*") as stream:
                for member in stream:
                    if member.isfile() and member.name in target_names:
                        hash_cache[member.name] = sha256_member(stream, member)
            tracking_by_hash: dict[str, list[str]] = defaultdict(list)
            for name in (name for names in tracking_by_stem.values() for name in names):
                member_hash = hash_cache.get(name, "")
                if member_hash:
                    tracking_by_hash[member_hash].append(name)
            for record in dut_rows:
                image_path = Path(record["image"])
                split_match = re.search(r"/images/(train|val|test)/DUT_\1_(\d+)\.jpg$", record["image"])
                number = split_match.group(2) if split_match else image_path.stem.rsplit("_", 1)[-1]
                split = split_match.group(1) if split_match else ""
                detection = f"DUT-Anti-UAV/detection/data/{split}/{split}/img/{number}.jpg" if split else ""
                annotation = f"DUT-Anti-UAV/detection/data/{split}/{split}/xml/{number}.xml" if split else ""
                record["source_archive"] = str(DUT_ARCHIVE.relative_to(ROOT))
                record["detection_member"] = detection if detection in members else ""
                record["annotation_member"] = annotation if annotation in members else ""
                if detection in members:
                    record["detection_hash"] = hash_cache[detection]
                    record["exact_archive_hash_match"] = record["detection_hash"] == record["image_hash"]
                candidates = tracking_by_stem.get(number, [])
                record["candidate_tracking_member_count"] = len(candidates)
                exact_tracking = tracking_by_hash.get(record["image_hash"], [])
                record["tracking_match_count"] = len(exact_tracking)
                record["tracking_exact_member_matches"] = "|".join(exact_tracking)
                record["provenance_status"] = classify_match(
                    exact_archive_member=record["exact_archive_hash_match"],
                    exact_tracking_members=exact_tracking,
                )
                if len(exact_tracking) == 1:
                    match = re.search(r"/((video\d+))/([^/]+\.jpg)$", exact_tracking[0])
                    if match:
                        video = match.group(2)
                        record["source_member"] = exact_tracking[0]
                        record["source_video_or_session"] = video
                        record["source_frame_index"] = Path(exact_tracking[0]).stem
                        record["source_sequence_key"] = f"DUT:{video}"
                        record["annotation_member"] = f"DUT-Anti-UAV/tracking/data/Anti-UAV-Tracking-V0/{video}_gt_first.txt"
                    record["evidence"] = "exact_detection_hash_and_unique_tracking_hash"
                elif len(exact_tracking) > 1:
                    record["source_member"] = "|".join(exact_tracking)
                    record["source_video_or_session"] = "ambiguous: " + "|".join(
                        sorted({re.search(r"/(video\d+)/", name).group(1) for name in exact_tracking})
                    )
                    record["source_frame_index"] = number
                    record["evidence"] = "exact_hash_matches_multiple_tracking_members; no promotion"
                elif record["exact_archive_hash_match"]:
                    record["evidence"] = "exact_detection_member_and_hash; no_tracking_sequence_match"
                else:
                    record["evidence"] = "no_exact_archive_hash_match"
                record["modality"] = "unknown"

    for record in records:
        record["checkpoint_sample_status"] = (
            "CONFIRMED_TRAIN_INPUT_SAMPLE" if record["v1_split"] == "train" else "CONFIRMED_NOT_TRAIN_INPUT_SAMPLE"
        )
    return records


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    fields = [
        "source", "image", "image_basename", "image_hash", "v2_group", "v1_split", "v1_group",
        "provenance_status", "source_archive", "source_member", "source_video_or_session",
        "source_frame_index", "modality", "annotation_member", "evidence", "detection_member",
        "detection_hash", "exact_archive_hash_match", "tracking_match_count",
        "tracking_exact_member_matches", "candidate_tracking_member_count", "source_sequence_key",
        "checkpoint_sample_status",
    ]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    input_payload, v1_rows, quarantine = input_audit()
    v1_by_key = {(row.get("source", ""), row.get("image", "")): row for row in v1_rows}
    records = audit_archive_members(quarantine, v1_by_key)
    if len(records) != 6505 or Counter(row["provenance_status"] for row in records).total() != 6505:
        raise RuntimeError("Scope 11 accounting invariant failed")

    write_csv(RUNTIME / "quarantine_provenance.csv", records)
    status_counts = Counter(row["provenance_status"] for row in records)
    source_status_counts = {source: dict(Counter(r["provenance_status"] for r in records if r["source"] == source)) for source in sorted({r["source"] for r in records})}
    dump_json(RUNTIME / "quarantine_provenance_summary.json", {
        "total_records": len(records), "status_counts": dict(status_counts),
        "source_status_counts": source_status_counts,
        "required_statuses": ["CONFIRMED_SOURCE_SEQUENCE", "CONFIRMED_INDEPENDENT_IMAGE", "POSSIBLE_MATCH", "UNRESOLVED"],
        "independent_image_rule": "No sample is confirmed independent without explicit source metadata; flat my_dataset archive remains UNRESOLVED.",
    })

    aliases = group_aliases(records)
    verified = [r for r in v1_rows if r.get("source") != "" and r.get("group") not in {x["v2_group"] for x in records}]
    quarantined_hashes = {r["image_hash"] for r in records}
    verified_hashes = {r.get("image_hash", "") for r in verified}
    exact_hash_collisions = sorted(quarantined_hashes & verified_hashes - {""})
    qpaths = {(r["source"], r["image"]) for r in records}
    vpaths = {(r.get("source", ""), r.get("image", "")) for r in verified}
    quarantine_hash_counts = Counter(r["image_hash"] for r in records)
    collision_payload = {
        "source_group_aliases": aliases,
        "exact_duplicate_hashes_quarantine_vs_verified": exact_hash_collisions,
        "exact_duplicate_path_count_quarantine_vs_verified": len(qpaths & vpaths),
        "exact_duplicate_hash_group_count_within_quarantine": sum(count > 1 for count in quarantine_hash_counts.values()),
        "exact_duplicate_row_count_within_quarantine": sum(count - 1 for count in quarantine_hash_counts.values() if count > 1),
        "same_source_video_session_status": "reported_by_source_group_aliases_only; no silent merge",
        "near_duplicate_screening": "NOT_RUN; no pHash promoted to evidence",
        "verified_reference_sample_count": len(verified),
    }
    dump_json(RUNTIME / "source_group_collisions.json", collision_payload)

    checkpoint = {
        "model_id": "yolov8n",
        "checkpoint_provenance_files": [
            "artifacts/benchmarks/model-selection/yolov8n/provenance.json",
            "artifacts/releases/yolov8n/release.json",
            "artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2/anti_drone_provenance.json",
        ],
        "v1_manifest_sha256": input_payload["observed_hashes"]["v1_manifest"],
        "v1_sample_split_counts": dict(Counter(r["v1_split"] for r in records)),
        "checkpoint_sample_status_counts": dict(Counter(r["checkpoint_sample_status"] for r in records)),
        "archive_member_video_key_in_checkpoint": False,
        "training_relation": "Sample-level V1 train membership is evidenced by the V1 manifest; source-sequence disjointness is not evidenced by checkpoint metadata.",
        "status": "SPLIT_UNVERIFIED",
        "halmstad_independence_inference": "NOT MADE",
    }
    dump_json(RUNTIME / "checkpoint_provenance.json", checkpoint)

    outputs = [p for p in RUNTIME.iterdir() if p.is_file() and p.name != "output_checksums.json"]
    output_checksums = {p.name: sha256_file(p) for p in sorted(outputs)}
    dump_json(RUNTIME / "output_checksums.json", output_checksums)
    print(json.dumps({"input": input_payload, "status_counts": dict(status_counts), "aliases": aliases, "outputs": output_checksums}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
