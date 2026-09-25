"""Audit provenance semantics of the 30,227 assigned RGBT rows."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "data/processed/drone-single-class-v2/manifest.json"
V2_REGISTRY = ROOT / "data/processed/drone-single-class-v2/split_registry.json"
OUT = ROOT / ".runtime/scope12"
PATTERN = re.compile(r"^RGBT_(train|val|test)_(\d{8})_(\d{6})_(\d+)_(\d+)_(visible|infrared)_(\d+)\.jpg$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    assigned = [row for row in v2["samples"] if row.get("assignment_status") == "ASSIGNED"]
    group_records: dict[str, dict] = {}
    session_groups: dict[str, set[str]] = defaultdict(set)
    session_splits: dict[str, set[str]] = defaultdict(set)
    rows = []
    errors = []
    for row in assigned:
        name = Path(row["image"]).name
        match = PATTERN.match(name)
        if not match:
            errors.append({"type": "filename_schema", "image": row["image"]})
            continue
        source_split, date, clock, stream_id, sequence_id, modality, frame = match.groups()
        derived_group = f"base:RGBT_{source_split}_{date}_{clock}_{stream_id}_{sequence_id}"
        session_key = f"RGBT_{source_split}_{date}_{clock}"
        if derived_group != row["group"]:
            errors.append({"type": "group_derivation_mismatch", "image": row["image"], "manifest_group": row["group"], "derived_group": derived_group})
        source_image = Path(row["image"])
        source_label = Path(row["label"]) if row.get("label") else None
        exists = source_image.is_file() and source_label is not None and source_label.is_file()
        hash_match = exists and sha256(source_image) == row["image_hash"]
        if not exists or not hash_match:
            errors.append({"type": "source_path_or_hash", "image": row["image"], "exists": exists, "hash_match": hash_match})
        session_groups[session_key].add(row["group"])
        session_splits[session_key].add(row["split"])
        record = group_records.setdefault(row["group"], {
            "group": row["group"],
            "source": row["source"],
            "derived_source_sequence_key": derived_group,
            "source_archive_member": None,
            "archive_level_status": "UNVERIFIED_ARCHIVE_MEMBER",
            "source_path_status": "CONFIRMED_LOCAL_PATH_AND_HASH" if hash_match else "UNRESOLVED",
            "modalities": set(),
            "frame_indices": [],
            "splits": set(),
            "sample_count": 0,
        })
        record["modalities"].add(modality)
        record["frame_indices"].append(int(frame))
        record["splits"].add(row["split"])
        record["sample_count"] += 1
        rows.append({
            "source": row["source"], "image": row["image"], "group": row["group"], "split": row["split"],
            "source_sequence_key": derived_group, "session_key_candidate": session_key,
            "modality": modality, "frame_index": int(frame), "source_path_exists": exists,
            "source_image_hash_match": hash_match,
            "archive_member": None, "archive_status": "UNVERIFIED_ARCHIVE_MEMBER",
        })

    groups = []
    for record in group_records.values():
        record["modalities"] = sorted(record["modalities"])
        frame_indices = record.pop("frame_indices")
        record["frame_index_min"] = min(frame_indices)
        record["frame_index_max"] = max(frame_indices)
        record["splits"] = sorted(record["splits"])
        groups.append(record)
    possible_sessions = [
        {"session_key_candidate": key, "groups": sorted(groups), "splits": sorted(session_splits[key]), "requires_archive_confirmation": True}
        for key, groups in sorted(session_groups.items()) if len(groups) > 1
    ]
    collisions = [item for item in possible_sessions if len(item["splits"]) > 1]
    result = {
        "status": "PASS" if not errors else "FAIL",
        "assigned_samples": len(assigned),
        "verified_group_count": len(group_records),
        "source_path_and_hash_confirmed_samples": sum(row["source_image_hash_match"] for row in rows),
        "archive_member_confirmed_samples": 0,
        "groups_with_archive_member_proof": 0,
        "modalities": dict(Counter(row["modality"] for row in rows)),
        "filename_schema_errors": errors,
        "possible_shared_session_candidates": len(possible_sessions),
        "possible_shared_session_candidates_crossing_splits": len(collisions),
        "possible_shared_session_note": "The date/time prefix is a candidate session key only. It is not promoted to SOURCE_GROUP_ALIAS without archive/session metadata.",
        "groups": groups,
        "cross_split_session_candidates": collisions,
        "source_archive_evidence": "V1/V2 manifests preserve local source paths and RGBT filename fields, but no archive/member key for the base rows; archive-level source independence remains unverified.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "source_provenance.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    with (OUT / "source_provenance_rows.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "assigned_samples", "verified_group_count", "source_path_and_hash_confirmed_samples", "possible_shared_session_candidates", "possible_shared_session_candidates_crossing_splits")}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
