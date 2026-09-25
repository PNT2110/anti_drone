"""Scope 14: audit original Anti-UAV300 partitions and dry-run V3 policies."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts.scope14_policy import deterministic_prefix_target_assignment, holdout_conflict, overlap_by_key, strict_original_split_assignment
except ModuleNotFoundError:
    from scope14_policy import deterministic_prefix_target_assignment, holdout_conflict, overlap_by_key, strict_original_split_assignment


ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT / "data/processed/drone-single-class/manifest.json"
V1_REGISTRY = ROOT / "data/processed/drone-single-class/split_registry.json"
V2 = ROOT / "data/processed/drone-single-class-v2/manifest.json"
V2_REGISTRY = ROOT / "data/processed/drone-single-class-v2/split_registry.json"
V2_AUDIT = ROOT / "data/processed/drone-single-class-v2/audit.json"
EXEC_MANIFEST = ROOT / "data/processed/drone-single-class-v2-executable/manifest.json"
EXEC_YAML = ROOT / "data/processed/drone-single-class-v2-executable/data.yaml"
SCOPE12 = ROOT / ".runtime/scope12/source_provenance.json"
S13_MAP = ROOT / ".runtime/scope13/rgbt_archive_mapping.csv"
S13_PREFIX = ROOT / ".runtime/scope13/session_prefix_audit.csv"
S13_SUMMARY = ROOT / ".runtime/scope13/rgbt_provenance_summary.json"
CHECKPOINT = ROOT / "artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2/weights/best.pt"
ARCHIVE = ROOT / "data/import_data_rar/Anti-UAV300.tar"
OUT = ROOT / ".runtime/scope14"

EXPECTED = {
    "v1_manifest": "3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d",
    "v1_registry": "7bc14c2e05b690f2df6c0cfb92e03b565a200f16dd0ef110df8e464837a63a54",
    "v2_manifest": "9605532a2b24566b691554125074c37f198c452bce343883b2a6720847299aa1",
    "v2_registry": "5819f6df78156561f3907e0eac05186dd5d77fe556699c74bad0ee5d40f51ed9",
    "v2_audit": "ab6a02db3b5efdff5f4c95d130ab4f9b06eddd18b9541aa7157ebb86f016a120",
    "exec_manifest": "c66e201aae060b96687c841d54a3297a1ea9fe7788d9101521bffe87f43db9aa",
    "exec_yaml": "38dabc580af21f5ed36f1d578f6b00c99f7efc9300ae72d105c6d44909cf8216",
    "scope12_source_provenance": "3ad585d1a696cee996684a7928ba62901181ac0bb3566c50c8ed9d838a3b3f95",
    "scope13_mapping": "ffb0d14247ff02f9d30e14011769435fd296103e4fe735e02abbb30cd1396d4e",
    "scope13_prefix": "84c3d1c9f09c472b1936fda629a9e46da97c7029a0984efebe580e593656537c",
    "scope13_summary": "baa3f6153e8d4c7aaeb9f9e6cfa7d94e4253715979598d955e957c92ddd7d657",
    "checkpoint": "662fbc1c066041345970f4211a6ceb9209907a331fd1724c0b2be7e53a4beec1",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def original_split_from_member(member: str) -> str:
    match = re.search(r"/Anti-UAV300/(train|val|test)/", member)
    if not match:
        raise ValueError(member)
    return match.group(1)


def safe_int(value: Any) -> int:
    return int(value)


def main() -> int:
    paths = {
        "v1_manifest": V1, "v1_registry": V1_REGISTRY, "v2_manifest": V2,
        "v2_registry": V2_REGISTRY, "v2_audit": V2_AUDIT, "exec_manifest": EXEC_MANIFEST,
        "exec_yaml": EXEC_YAML, "scope12_source_provenance": SCOPE12, "scope13_mapping": S13_MAP,
        "scope13_prefix": S13_PREFIX, "scope13_summary": S13_SUMMARY, "checkpoint": CHECKPOINT,
    }
    observed = {key: sha256(path) for key, path in paths.items()}
    if observed != EXPECTED:
        raise RuntimeError(f"BLOCKED: Scope 14 baseline mismatch: {observed}")
    v2 = json.loads(V2.read_text(encoding="utf-8"))
    source_provenance = json.loads(SCOPE12.read_text(encoding="utf-8"))
    mapping = list(csv.DictReader(S13_MAP.open(encoding="utf-8")))
    if len(mapping) != 30227 or len({row["group"] for row in mapping}) != 318:
        raise RuntimeError("BLOCKED: Scope 13 mapping baseline counts mismatch")
    if source_provenance["possible_shared_session_candidates"] != 59 or source_provenance["possible_shared_session_candidates_crossing_splits"] != 47:
        raise RuntimeError("BLOCKED: Scope 12 candidate prefix baseline mismatch")

    with tarfile.open(ARCHIVE, "r:") as archive:
        label_split_groups: dict[str, set[str]] = {}
        for split in ("train", "val", "test"):
            member = f"Anti-UAV300/data/Anti-UAV300/label_new/{split}.json"
            with archive.extractfile(member) as stream:
                label_split_groups[split] = set(json.load(stream))
    archive_sequence_split = {}
    for row in mapping:
        source_split = original_split_from_member(row["source_video_member"])
        seq = row["source_sequence_id"]
        previous = archive_sequence_split.setdefault(seq, source_split)
        if previous != source_split:
            raise RuntimeError(f"BLOCKED: sequence mapped to two original source splits: {seq}")
    label_membership_errors = []
    for seq, source_split in archive_sequence_split.items():
        memberships = [split for split, groups in label_split_groups.items() if seq in groups]
        if memberships != [source_split]:
            label_membership_errors.append({"sequence": seq, "path_split": source_split, "label_new_memberships": memberships})
    if label_membership_errors:
        raise RuntimeError(f"BLOCKED: label_new/source path split mismatch: {len(label_membership_errors)}")

    rows = []
    v2_by_image = {(item["source"], item["image"]): item for item in v2["samples"]}
    for row in mapping:
        v2_row = v2_by_image.get((row.get("source", "base"), row["image"]))
        if v2_row is None:
            # Scope 13 mapping rows are base-only; keep the lookup explicit so
            # a missing source row cannot silently enter a dry run.
            raise RuntimeError(f"BLOCKED: mapping row absent from V2: {row['image']}")
        rows.append(row | {
            "original_source_split": original_split_from_member(row["source_video_member"]),
            "candidate_prefix": row["source_session_prefix"],
            "source_sequence": row["source_sequence_id"],
            "mapping_status": "CONFIRMED",
            "source": v2_row["source"],
            "image_hash": v2_row["image_hash"],
            "assignment_status": v2_row["assignment_status"],
        })
    prefix_data: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = prefix_data.setdefault(row["candidate_prefix"], {"prefix": row["candidate_prefix"], "sample_count": 0, "groups": set(), "sequences": set(), "original_source_splits": set(), "modalities": Counter(), "v2_splits": set()})
        item["sample_count"] += 1
        item["groups"].add(row["group"])
        item["sequences"].add(row["source_sequence"])
        item["original_source_splits"].add(row["original_source_split"])
        item["modalities"][row["modality"]] += 1
        item["v2_splits"].add(row["split"])
    prefix_groups = []
    for item in prefix_data.values():
        item["groups"] = sorted(item["groups"]); item["sequences"] = sorted(item["sequences"])
        item["original_source_splits"] = sorted(item["original_source_splits"]); item["v2_splits"] = sorted(item["v2_splits"])
        item["modalities"] = dict(item["modalities"])
        prefix_groups.append(item)

    # Option A is read directly from accepted V2 assignment.
    option_a = {"name": "V2_CURRENT_SEQUENCE_ATOMIC", "rows": rows, "status": "BASELINE_NOT_REBUILT"}
    # Option B strict mode keeps the official source partition as a boundary.
    option_b_rows = []
    for row in rows:
        proposed = strict_original_split_assignment(row["original_source_split"])
        option_b_rows.append(row | {"split": proposed, "assignment_policy": "PREFIX_ATOMIC_PLUS_ORIGINAL_SOURCE_SPLIT_BOUNDARY"})
    option_b_groups = {item["prefix"]: strict_original_split_assignment(item["original_source_splits"][0]) for item in prefix_groups}
    target_assignment = deterministic_prefix_target_assignment(prefix_groups, seed=42)
    target_conflicts = []
    for item in prefix_groups:
        proposed = target_assignment[item["prefix"]]
        original = item["original_source_splits"]
        if any(holdout_conflict(source_split, proposed) for source_split in original):
            target_conflicts.append({"prefix": item["prefix"], "original_source_splits": original, "proposed_target_split": proposed, "sample_count": item["sample_count"], "status": "BLOCKED_BY_ORIGINAL_HOLDOUT_BOUNDARY"})
    target_rows = [row | {"split": target_assignment[row["candidate_prefix"]], "assignment_policy": "PREFIX_ATOMIC_TARGET_PREVIEW_BLOCKED_BY_SOURCE_BOUNDARY"} for row in rows]

    matrix = Counter((row["original_source_split"], row["split"]) for row in rows)
    matrix_sequences = Counter((archive_sequence_split[row["source_sequence"]], row["split"]) for row in {r["source_sequence"]: r for r in rows}.values())
    matrix_prefixes = Counter((item["original_source_splits"][0], split) for item in prefix_groups for split in item["v2_splits"])
    source_split_counts = Counter(row["original_source_split"] for row in rows)
    source_sequence_counts = Counter(archive_sequence_split.values())
    prefix_count_by_source = Counter(item["original_source_splits"][0] for item in prefix_groups)
    candidate_prefix_count_by_source = Counter(item["original_source_splits"][0] for item in prefix_groups if len(item["groups"]) > 1)

    def audit_assignment(assignment_rows: list[dict], *, prefix_atomic: bool) -> dict:
        groups_by_split = defaultdict(set); prefixes_by_split = defaultdict(set); sequences_by_split = defaultdict(set); paths_by_split = defaultdict(set); hashes_by_split = defaultdict(set)
        for row in assignment_rows:
            groups_by_split[row["split"]].add(row["group"]); prefixes_by_split[row["split"]].add(row["candidate_prefix"]); sequences_by_split[row["split"]].add(row["source_sequence"]); paths_by_split[row["split"]].add(row["image"]); hashes_by_split[row["split"]].add(row["image_hash"])
        def pair_overlap(buckets):
            return {(a, b): len(buckets[a] & buckets[b]) for a in ("train", "val", "test") for b in ("train", "val", "test") if a < b and buckets[a] & buckets[b]}
        return {
            "sample_count": len(assignment_rows), "split_counts": dict(Counter(row["split"] for row in assignment_rows)),
            "source_sequence_overlap": pair_overlap(sequences_by_split), "candidate_prefix_overlap": pair_overlap(prefixes_by_split) if prefix_atomic else None,
            "source_path_overlap": pair_overlap(paths_by_split), "source_hash_overlap": pair_overlap(hashes_by_split),
            "quarantine_rows_in_assignment": sum(row.get("assignment_status") == "QUARANTINED" for row in assignment_rows),
            "groups_cross_split": len(overlap_by_key(assignment_rows, "group")), "prefixes_cross_split": len(overlap_by_key(assignment_rows, "candidate_prefix")),
            "session_disjoint": "UNVERIFIED",
        }
    audit_a = audit_assignment(rows, prefix_atomic=False)
    audit_b = audit_assignment(option_b_rows, prefix_atomic=True)
    audit_target = audit_assignment(target_rows, prefix_atomic=True)

    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "input_audit.json", {"status": "PASS", "observed_checksums": observed, "baseline": {"assigned_samples": len(rows), "quarantine_samples": 6505, "source_sequences": len(archive_sequence_split), "total_prefixes": len(prefix_groups), "candidate_prefixes": sum(len(item["groups"]) > 1 for item in prefix_groups), "cross_split_prefixes": sum(len(item["v2_splits"]) > 1 for item in prefix_groups), "archive_label_split_membership_errors": len(label_membership_errors)}, "no_artifact_modified": True})
    with (OUT / "original_source_split_matrix.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["original_source_split", "v2_split", "sample_count", "source_sequence_count", "candidate_prefix_count"]
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for original in ("train", "val", "test"):
            for v2_split in ("train", "val", "test"):
                seq_count = len({seq for seq, source in archive_sequence_split.items() if source == original and any(row["source_sequence"] == seq and row["split"] == v2_split for row in rows)})
                prefix_count = len({item["prefix"] for item in prefix_groups if item["original_source_splits"] == [original] and v2_split in item["v2_splits"]})
                writer.writerow({"original_source_split": original, "v2_split": v2_split, "sample_count": matrix[(original, v2_split)], "source_sequence_count": seq_count, "candidate_prefix_count": prefix_count})

    def write_dry(path: Path, values: list[dict]) -> None:
        fields = ["image", "group", "candidate_prefix", "source_sequence", "original_source_split", "split", "modality", "assignment_policy"]
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows({field: row.get(field, "") for field in fields} for row in values)
    write_dry(OUT / "v3_dry_run_a.csv", rows)
    write_dry(OUT / "v3_dry_run_b_conservative.csv", option_b_rows)
    write_dry(OUT / "v3_dry_run_b_target_blocked.csv", target_rows)
    write_json(OUT / "v3_dry_run_audit.json", {"option_a": audit_a, "option_b_conservative": audit_b, "option_b_target_preview": audit_target, "target_preview_conflicts": target_conflicts, "target_preview_conflict_sample_count": sum(item["sample_count"] for item in target_conflicts), "candidate_prefix_groups": prefix_groups, "source_sequence_split": archive_sequence_split, "source_split_counts": dict(source_split_counts), "source_sequence_counts": dict(source_sequence_counts), "prefix_count_by_source_split": dict(prefix_count_by_source), "candidate_prefix_count_by_source_split": dict(candidate_prefix_count_by_source), "original_holdout_evidence": "Anti-UAV300 directory train/val/test plus label_new/{train,val,test}.json membership agree for all 318 sequences; archive does not separately state statistical independence.", "original_source_split_matrix": {f"{a}__{b}": matrix[(a, b)] for a in ("train", "val", "test") for b in ("train", "val", "test")}, "matrix_sequences": {f"{a}__{b}": matrix_sequences[(a, b)] for a in ("train", "val", "test") for b in ("train", "val", "test")}, "matrix_prefixes": {f"{a}__{b}": matrix_prefixes[(a, b)] for a in ("train", "val", "test") for b in ("train", "val", "test")}, "seed": 42, "target_ratio": {"train": 0.7, "val": 0.2, "test": 0.1}, "no_production_v3": True})
    print(json.dumps({"status": "PASS", "option_a": audit_a, "option_b_conservative": audit_b, "target_preview_conflicts": len(target_conflicts), "target_preview_blocked_samples": sum(item["sample_count"] for item in target_conflicts)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
