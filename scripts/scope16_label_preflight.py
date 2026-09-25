"""Scope 16 label/source-annotation preflight.

This is a read-only gate.  It does not repair labels, alter splits, or start
training.  The Anti-UAV300 JSON metadata is read directly from the archive so
an empty processed YOLO label is not silently treated as a negative.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v3-candidate"
MANIFEST = DATASET / "manifest.json"
REGISTRY = DATASET / "split_registry.json"
ARCHIVE = ROOT / "data/import_data_rar/Anti-UAV300.tar"
DIRECT_AUDIT = ROOT / ".runtime/scope15/direct_disk_audit.json"
OUT = ROOT / ".runtime/scope16/label_preflight.json"
MISMATCHES = ROOT / ".runtime/scope16/label_source_mismatches.jsonl"
EXPECTED_MANIFEST = "b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc"
EXPECTED_REGISTRY = "57ffb56effd35ad65aad9d163e586ebd8c9f9f1f19c93a86d5fd7619d72cff3d"
EXPECTED_COUNTS = {"train": 12142, "val": 8237, "test": 9848}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_label(path: Path) -> tuple[int, Counter[str], list[str]]:
    objects = 0
    classes: Counter[str] = Counter()
    errors: list[str] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="strict").splitlines(), 1):
        fields = raw.split()
        if len(fields) != 5:
            errors.append(f"{path}:{line_no}: expected 5 fields")
            continue
        try:
            values = [float(value) for value in fields]
        except ValueError:
            errors.append(f"{path}:{line_no}: non-numeric label")
            continue
        classes[str(int(values[0])) if values[0].is_integer() else str(values[0])] += 1
        if values[0] != 0:
            errors.append(f"{path}:{line_no}: class id {values[0]} outside schema")
        if any(not 0.0 <= value <= 1.0 for value in values[1:]) or values[3] <= 0 or values[4] <= 0:
            errors.append(f"{path}:{line_no}: invalid normalized bbox")
        epsilon = 1e-6
        if values[1] - values[3] / 2 < -epsilon or values[1] + values[3] / 2 > 1 + epsilon or values[2] - values[4] / 2 < -epsilon or values[2] + values[4] / 2 > 1 + epsilon:
            errors.append(f"{path}:{line_no}: bbox exceeds image bounds")
        objects += 1
    return objects, classes, errors


def main() -> int:
    errors: list[str] = []
    if sha256(MANIFEST) != EXPECTED_MANIFEST:
        errors.append("candidate manifest checksum mismatch")
    if sha256(REGISTRY) != EXPECTED_REGISTRY:
        errors.append("candidate split registry checksum mismatch")
    direct_audit = json.loads(DIRECT_AUDIT.read_text(encoding="utf-8"))
    if direct_audit.get("status") != "PASS":
        errors.append("Scope 15 direct-disk audit is not PASS")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = manifest["samples"]
    if len(rows) != 30227:
        errors.append(f"manifest sample count {len(rows)} != 30227")

    split_stats: dict[str, Counter[str]] = defaultdict(Counter)
    modality_stats: dict[str, Counter[str]] = defaultdict(Counter)
    class_distribution: Counter[str] = Counter()
    annotation_cache: dict[str, dict] = {}
    mismatch_rows: list[dict] = []
    abnormal_rows: list[dict] = []
    total_objects = 0
    with tarfile.open(ARCHIVE, "r") as archive:
        for row in rows:
            split = row["candidate_split"]
            modality = row["modality"]
            split_stats[split]["images"] += 1
            modality_stats[modality]["images"] += 1
            label_path = Path(row["source_label"])
            if not label_path.is_file():
                split_stats[split]["missing_or_corrupt_annotation"] += 1
                modality_stats[modality]["missing_or_corrupt_annotation"] += 1
                abnormal_rows.append({"sample_id": row["sample_id"], "reason": "missing_label", "path": str(label_path)})
                continue
            objects, classes, label_errors = inspect_label(label_path)
            total_objects += objects
            class_distribution.update(classes)
            split_stats[split]["objects"] += objects
            split_stats[split]["labeled_images"] += bool(objects)
            split_stats[split]["empty_labels"] += not bool(objects)
            modality_stats[modality]["objects"] += objects
            modality_stats[modality]["labeled_images"] += bool(objects)
            modality_stats[modality]["empty_labels"] += not bool(objects)
            if label_errors:
                split_stats[split]["invalid_or_abnormal"] += len(label_errors)
                modality_stats[modality]["invalid_or_abnormal"] += len(label_errors)
                abnormal_rows.append({"sample_id": row["sample_id"], "reason": "invalid_label", "details": label_errors})

            member = row["source_annotation_member"]
            if member not in annotation_cache:
                try:
                    annotation_cache[member] = json.load(archive.extractfile(member))
                except Exception as exc:
                    errors.append(f"cannot read annotation member {member}: {exc}")
                    annotation_cache[member] = {}
            annotation = annotation_cache[member]
            frame = row["source_frame_index"]
            exist = annotation.get("exist", [])
            gt_rect = annotation.get("gt_rect", [])
            if not isinstance(frame, int) or frame < 0 or frame >= len(exist) or frame >= len(gt_rect):
                reason = "missing_or_corrupt_annotation"
                errors.append(f"annotation frame out of range: {row['sample_id']}")
            else:
                source_positive = bool(exist[frame]) and bool(gt_rect[frame])
                label_positive = bool(objects)
                if source_positive:
                    split_stats[split]["source_confirmed_positive"] += 1
                    modality_stats[modality]["source_confirmed_positive"] += 1
                    if label_positive:
                        split_stats[split]["source_label_presence_consistent"] += 1
                        modality_stats[modality]["source_label_presence_consistent"] += 1
                        reason = "consistent_positive"
                    else:
                        split_stats[split]["missing_or_corrupt_annotation"] += 1
                        modality_stats[modality]["missing_or_corrupt_annotation"] += 1
                        reason = "MISSING_OR_CORRUPT_ANNOTATION"
                        mismatch_rows.append({"sample_id": row["sample_id"], "split": split, "modality": modality, "source_annotation_member": member, "source_frame_index": frame, "source_exist": exist[frame], "source_gt_rect": gt_rect[frame], "label_path": str(label_path), "classification": reason})
                elif not exist[frame] and not gt_rect[frame]:
                    split_stats[split]["confirmed_negative"] += 1
                    modality_stats[modality]["confirmed_negative"] += 1
                    reason = "CONFIRMED_NEGATIVE"
                else:
                    split_stats[split]["unverified_empty_label"] += 1
                    modality_stats[modality]["unverified_empty_label"] += 1
                    reason = "UNVERIFIED_EMPTY_LABEL"
                    if not label_positive:
                        mismatch_rows.append({"sample_id": row["sample_id"], "split": split, "modality": modality, "source_annotation_member": member, "source_frame_index": frame, "source_exist": exist[frame], "source_gt_rect": gt_rect[frame], "label_path": str(label_path), "classification": reason})

    for split, expected in EXPECTED_COUNTS.items():
        if split_stats[split]["images"] != expected:
            errors.append(f"{split} image count mismatch")
    if mismatch_rows:
        errors.append(f"{len(mismatch_rows)} processed labels are empty/nonmatching while archive annotation indicates a target")
    status = "PASS" if not errors and not abnormal_rows else "PREFLIGHT_BLOCKED"
    result = {
        "status": status,
        "training_started": False,
        "dataset_manifest_sha256": sha256(MANIFEST),
        "split_registry_sha256": sha256(REGISTRY),
        "sample_count": len(rows),
        "split_stats": {key: dict(value) for key, value in sorted(split_stats.items())},
        "modality_stats": {key: dict(value) for key, value in sorted(modality_stats.items())},
        "class_distribution": dict(class_distribution),
        "total_labeled_objects": total_objects,
        "annotation_member_count": len(annotation_cache),
        "mismatch_count": len(mismatch_rows),
        "abnormal_row_count": len(abnormal_rows),
        "errors": errors,
        "classification_policy": {
            "CONFIRMED_NEGATIVE": "archive exist=0 and gt_rect empty",
            "UNVERIFIED_EMPTY_LABEL": "empty label without a confirmed negative source state",
            "MISSING_OR_CORRUPT_ANNOTATION": "archive says target exists but processed label is empty or malformed",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    with MISMATCHES.open("w", encoding="utf-8") as stream:
        for row in mismatch_rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
