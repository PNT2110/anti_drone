"""Resolve V2 RGBT groups against Anti-UAV300 archive members.

Only archive headers/JSON metadata for all groups and a small, deterministic
set of representative video frames are read.  The archive is never expanded
wholesale and V1/V2/executable artifacts are read-only inputs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

try:
    from scripts.scope13_provenance import classify_prefix, parse_rgbt_basename
except ModuleNotFoundError:
    from scope13_provenance import classify_prefix, parse_rgbt_basename


ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "data/processed/drone-single-class/manifest.json"
V1_REGISTRY = ROOT / "data/processed/drone-single-class/split_registry.json"
V2 = ROOT / "data/processed/drone-single-class-v2/manifest.json"
V2_REGISTRY = ROOT / "data/processed/drone-single-class-v2/split_registry.json"
V2_AUDIT = ROOT / "data/processed/drone-single-class-v2/audit.json"
EXEC_MANIFEST = ROOT / "data/processed/drone-single-class-v2-executable/manifest.json"
EXEC_YAML = ROOT / "data/processed/drone-single-class-v2-executable/data.yaml"
SCOPE12_PROVENANCE = ROOT / ".runtime/scope12/source_provenance.json"
ARCHIVE = ROOT / "data/import_data_rar/Anti-UAV300.tar"
OUT = ROOT / ".runtime/scope13"

BASELINE = {
    "v1_manifest": "3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d",
    "v1_registry": "7bc14c2e05b690f2df6c0cfb92e03b565a200f16dd0ef110df8e464837a63a54",
    "v2_manifest": "9605532a2b24566b691554125074c37f198c452bce343883b2a6720847299aa1",
    "v2_registry": "5819f6df78156561f3907e0eac05186dd5d77fe556699c74bad0ee5d40f51ed9",
    "v2_audit": "ab6a02db3b5efdff5f4c95d130ab4f9b06eddd18b9541aa7157ebb86f016a120",
    "exec_manifest": "c66e201aae060b96687c841d54a3297a1ea9fe7788d9101521bffe87f43db9aa",
    "exec_yaml": "38dabc580af21f5ed36f1d578f6b00c99f7efc9300ae72d105c6d44909cf8216",
    "scope12_source_provenance": "3ad585d1a696cee996684a7928ba62901181ac0bb3566c50c8ed9d838a3b3f95",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_sequence_dir(parsed: dict) -> str:
    return "Anti-UAV300/data/Anti-UAV300/{split}/{sequence}".format(
        split=parsed["source_split"], sequence=parsed["archive_sequence_id"]
    )


def representative_groups(groups: list[str]) -> list[str]:
    if len(groups) <= 3:
        return groups
    return [groups[0], groups[len(groups) // 2], groups[-1]]


def decode_representatives(group_rows: dict[str, list[dict]], members: dict[str, tarfile.TarInfo], archive: tarfile.TarFile) -> list[dict]:
    selected = []
    groups = representative_groups(sorted(group_rows))
    for group in groups:
        rows = sorted(group_rows[group], key=lambda row: (row["modality"], row["source_frame_index"]))
        for modality in ("visible", "infrared"):
            candidates = [row for row in rows if row["modality"] == modality]
            if candidates:
                selected.append(candidates[0])
    evidence = []
    with tempfile.TemporaryDirectory(prefix="scope13-rep-") as temp:
        temp_path = Path(temp)
        for row in selected:
            video = members[row["source_video_member"]]
            video_path = temp_path / f"{len(evidence)}.mp4"
            with archive.extractfile(video) as stream, video_path.open("wb") as output:
                shutil.copyfileobj(stream, output)
            decoded = temp_path / f"{len(evidence)}.jpg"
            frame = row["source_frame_index"]
            decode_command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video_path),
                "-vf", f"select='eq(n,{frame})'", "-frames:v", "1", "-q:v", "2", str(decoded),
            ]
            subprocess.run(decode_command, check=True)
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames", "-of", "json", str(video_path)],
                check=True, capture_output=True, text=True,
            )
            probe_data = json.loads(probe.stdout)["streams"][0]
            import cv2
            import numpy as np

            source_image = cv2.imread(row["image"], cv2.IMREAD_UNCHANGED)
            decoded_image = cv2.imread(str(decoded), cv2.IMREAD_UNCHANGED)
            same_shape = source_image is not None and decoded_image is not None and source_image.shape == decoded_image.shape
            mean_abs = None
            max_abs = None
            if same_shape:
                delta = np.abs(source_image.astype(np.int16) - decoded_image.astype(np.int16))
                mean_abs = float(delta.mean())
                max_abs = int(delta.max())
            accepted = bool(same_shape and mean_abs is not None and mean_abs <= 10.0 and max_abs <= 64)
            evidence.append({
                "group": row["group"], "modality": row["modality"], "source_frame_index": frame,
                "source_video_member": row["source_video_member"], "source_image": row["image"],
                "source_image_shape": list(source_image.shape) if source_image is not None else None,
                "decoded_shape": list(decoded_image.shape) if decoded_image is not None else None,
                "mean_absolute_pixel_difference": mean_abs, "max_absolute_pixel_difference": max_abs,
                "video_probe": probe_data, "accepted_as_representative_corroboration": accepted,
                "decode_command": " ".join(decode_command),
                "transformation": "decode selected zero-based video frame; ffmpeg JPEG q=2 for comparison; no resize/crop",
                "comparison_rule": "same decoded dimensions, mean_abs <= 10, max_abs <= 64",
            })
    return evidence


def main() -> int:
    baseline_paths = {
        "v1_manifest": V1, "v1_registry": V1_REGISTRY, "v2_manifest": V2,
        "v2_registry": V2_REGISTRY, "v2_audit": V2_AUDIT, "exec_manifest": EXEC_MANIFEST,
        "exec_yaml": EXEC_YAML, "scope12_source_provenance": SCOPE12_PROVENANCE,
    }
    observed = {name: sha256(path) for name, path in baseline_paths.items()}
    if observed != BASELINE:
        raise RuntimeError(f"BLOCKED: Scope 13 baseline mismatch: {observed}")
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    scope12 = json.loads(SCOPE12_PROVENANCE.read_text(encoding="utf-8"))
    assigned = [row for row in v2["samples"] if row.get("assignment_status") == "ASSIGNED"]
    quarantine = [row for row in v2["samples"] if row.get("assignment_status") == "QUARANTINED"]
    if len(assigned) != 30227 or len(quarantine) != 6505 or len({row["group"] for row in assigned}) != 318:
        raise RuntimeError("BLOCKED: Scope 13 baseline counts mismatch")
    if scope12.get("possible_shared_session_candidates") != 59 or scope12.get("possible_shared_session_candidates_crossing_splits") != 47 or scope12.get("archive_member_confirmed_samples") != 0:
        raise RuntimeError("BLOCKED: Scope 12 provenance baseline counts mismatch")

    with tarfile.open(ARCHIVE, "r:") as archive:
        members = {member.name: member for member in archive.getmembers() if member.isfile()}
        group_rows: dict[str, list[dict]] = defaultdict(list)
        errors = []
        mapping_rows = []
        group_evidence = {}
        for row in assigned:
            parsed = parse_rgbt_basename(Path(row["image"]).name)
            if parsed is None or parsed["group"] != row["group"]:
                errors.append({"type": "filename_or_group_schema", "image": row["image"], "group": row["group"]})
                continue
            seq_dir = archive_sequence_dir(parsed)
            video_member = f"{seq_dir}/{parsed['modality']}.mp4"
            annotation_member = f"{seq_dir}/{parsed['modality']}.json"
            other_video = f"{seq_dir}/{('infrared' if parsed['modality'] == 'visible' else 'visible')}.mp4"
            if video_member not in members or annotation_member not in members or other_video not in members:
                errors.append({"type": "missing_archive_member", "group": row["group"], "video": video_member, "annotation": annotation_member})
                continue
            with archive.extractfile(members[annotation_member]) as stream:
                metadata = json.load(stream)
            frame = parsed["source_frame_index"]
            if frame >= len(metadata.get("exist", [])) or frame >= len(metadata.get("gt_rect", [])):
                errors.append({"type": "frame_index_out_of_range", "group": row["group"], "frame": frame, "length": len(metadata.get("exist", []))})
                continue
            parsed_row = row | {
                "mapping_status": "CONFIRMED",
                "source_archive": "data/import_data_rar/Anti-UAV300.tar",
                "source_video_member": video_member,
                "source_annotation_member": annotation_member,
                "source_sequence_id": parsed["archive_sequence_id"],
                "source_session_prefix": parsed["session_prefix"],
                "source_frame_index": frame,
                "modality": parsed["modality"],
                "archive_frame_exists": metadata["exist"][frame],
                "archive_frame_annotation": metadata["gt_rect"][frame],
                "source_fps": "not encoded in JSON; representative ffprobe below",
                "evidence_rule": "exact archive sequence directory + exact modality member + JSON frame index + validated RGBT naming rule",
                "content_transform_limit": "V1 JPEG bytes need not equal decoded MP4 bytes; representative decode is corroboration, not byte equality",
            }
            mapping_rows.append(parsed_row)
            group_rows[row["group"]].append(parsed_row)
            group_evidence.setdefault(row["group"], {"source_sequence_id": parsed["archive_sequence_id"], "archive_directory": seq_dir, "source_split": parsed["source_split"], "modalities": set(), "splits": set()})
            group_evidence[row["group"]]["modalities"].add(parsed["modality"])
            group_evidence[row["group"]]["splits"].add(row["split"])
        reps = decode_representatives(group_rows, members, archive)

    if errors or len(mapping_rows) != 30227 or len(group_rows) != 318:
        raise RuntimeError(f"BLOCKED: incomplete mapping errors={len(errors)} rows={len(mapping_rows)} groups={len(group_rows)}")
    if not all(item["accepted_as_representative_corroboration"] for item in reps):
        raise RuntimeError("BLOCKED: representative decode corroboration failed")

    for item in group_evidence.values():
        item["modalities"] = sorted(item["modalities"])
        item["splits"] = sorted(item["splits"])
        item["source_session_id"] = None
        item["session_status"] = "UNRESOLVED"
        item["sequence_status"] = "CONFIRMED_DISTINCT_SOURCE_SEQUENCE"
    prefix_groups: dict[str, set[str]] = defaultdict(set)
    prefix_splits: dict[str, set[str]] = defaultdict(set)
    for item in mapping_rows:
        prefix_groups[item["source_session_prefix"]].add(item["source_sequence_id"])
        prefix_splits[item["source_session_prefix"]].add(item["split"])
    prefix_rows = []
    for prefix in sorted(prefix_groups):
        source_status, session_status = classify_prefix(archive_sequence_ids=prefix_groups[prefix])
        prefix_rows.append({
            "session_prefix": prefix, "archive_sequence_ids": sorted(prefix_groups[prefix]),
            "groups": sorted({item["group"] for item in mapping_rows if item["source_session_prefix"] == prefix}),
            "splits": sorted(prefix_splits[prefix]), "cross_split": len(prefix_splits[prefix]) > 1,
            "source_status": source_status, "session_status": session_status,
            "explicit_session_id": None,
            "decision_reason": "distinct full archive sequence directories are confirmed; archive exposes no explicit session ID, so shared-session status remains unresolved",
        })
    sequence_collisions = []
    for sequence_id in sorted({item["source_sequence_id"] for item in mapping_rows}):
        splits = sorted({item["split"] for item in mapping_rows if item["source_sequence_id"] == sequence_id})
        if len(splits) > 1:
            sequence_collisions.append({"source_sequence_id": sequence_id, "splits": splits})
    session_collisions = [row for row in prefix_rows if row["cross_split"] and row["session_status"] == "CONFIRMED_SHARED_SESSION"]
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "rgbt_archive_mapping.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["image", "group", "split", "source_sequence_id", "source_session_prefix", "source_video_member", "source_annotation_member", "source_frame_index", "modality", "archive_frame_exists", "archive_frame_annotation", "mapping_status"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in mapping_rows)
    (OUT / "session_prefix_audit.csv").write_text("", encoding="utf-8")
    with (OUT / "session_prefix_audit.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["session_prefix", "archive_sequence_ids", "groups", "splits", "cross_split", "source_status", "session_status", "explicit_session_id", "decision_reason"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in prefix_rows:
            writer.writerow({field: "|".join(map(str, row[field])) if isinstance(row[field], list) else row[field] for field in fields})
    summary = {
        "status": "PARTIALLY_COMPLETE",
        "mapping_status": "CONFIRMED_REPRODUCIBLE_ARCHIVE_SCHEMA",
        "assigned_samples": len(mapping_rows), "verified_groups": len(group_rows),
        "archive_member_confirmed_samples": len(mapping_rows), "archive_member_confirmed_groups": len(group_rows),
        "mapping_archive": "Anti-UAV300.tar", "archive_sha256_from_accepted_inventory": "c8af3934b7b84c21f1ecfda4723c11b186a6c7182c1ece2b629ebc2035fa6e2f",
        "prefix_count": len(prefix_rows), "cross_split_prefix_count": sum(row["cross_split"] for row in prefix_rows),
        "prefix_source_status_counts": dict(Counter(row["source_status"] for row in prefix_rows)),
        "prefix_session_status_counts": dict(Counter(row["session_status"] for row in prefix_rows)),
        "confirmed_cross_split_sequence_collisions": len(sequence_collisions),
        "confirmed_cross_split_session_collisions": len(session_collisions),
        "session_relationship_unknown_cross_split_prefixes": sum(row["cross_split"] and row["session_status"] == "UNRESOLVED" for row in prefix_rows),
        "representative_decode_count": len(reps), "representative_decode_all_accepted": all(item["accepted_as_representative_corroboration"] for item in reps),
        "errors": errors, "representative_evidence": reps,
        "baseline_checksums": observed,
        "v2_unchanged": True, "quarantine_unchanged": True,
        "note": "Sequence-level archive mapping is resolved. Session-level independence is unresolved because the archive metadata has no explicit session ID; no V3 was created.",
    }
    (OUT / "rgbt_provenance_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "group_archive_evidence.json").write_text(json.dumps({key: value for key, value in sorted(group_evidence.items())}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("status", "assigned_samples", "verified_groups", "archive_member_confirmed_samples", "prefix_count", "cross_split_prefix_count", "prefix_source_status_counts", "prefix_session_status_counts", "confirmed_cross_split_sequence_collisions", "confirmed_cross_split_session_collisions", "representative_decode_count")}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
