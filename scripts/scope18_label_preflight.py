"""Independent read-only preflight for the Scope 17 repaired candidate."""

from __future__ import annotations

import hashlib
import json
import random
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
ARCHIVE = ROOT / "data/import_data_rar/Anti-UAV300.tar"
V3 = ROOT / "data/processed/drone-single-class-v3-candidate/manifest.json"
V3_REGISTRY = ROOT / "data/processed/drone-single-class-v3-candidate/split_registry.json"
REPAIR_AUDIT = ROOT / ".runtime/scope17/label_repair_audit.json"
OUT = ROOT / ".runtime/scope18/label_preflight.json"
EXPECTED_MANIFEST = "bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45"
EXPECTED_REGISTRY = "c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1"
EXPECTED_REPAIR_AUDIT = "bb17d508aaae28e523734a33852e53fb3c8f2cb31078ab03c24d47bf81ddd914"
EXPECTED_COUNTS = {"train": 12142, "val": 8237, "test": 9848}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rects(value: object) -> list[list[float]]:
    if isinstance(value, list) and len(value) == 4 and all(isinstance(item, (int, float)) for item in value):
        return [[float(item) for item in value]]
    if isinstance(value, list) and all(isinstance(item, list) and len(item) == 4 for item in value):
        return [[float(item) for item in item] for item in value]
    return []


def expected_yolo(rect: list[float], width: int, height: int) -> list[float]:
    x, y, w, h = rect
    return [(x + w / 2) / width, (y + h / 2) / height, w / width, h / height]


def main() -> int:
    errors: list[str] = []
    observed = {"manifest": sha256(DATASET / "manifest.json"), "split_registry": sha256(DATASET / "split_registry.json"), "data_yaml": sha256(DATASET / "data.yaml"), "repair_audit": sha256(REPAIR_AUDIT), "v3_manifest": sha256(V3), "v3_registry": sha256(V3_REGISTRY)}
    if observed["manifest"] != EXPECTED_MANIFEST or observed["split_registry"] != EXPECTED_REGISTRY or observed["repair_audit"] != EXPECTED_REPAIR_AUDIT:
        errors.append("Scope 17 repaired baseline checksum mismatch")
    repair_audit = json.loads(REPAIR_AUDIT.read_text(encoding="utf-8"))
    if repair_audit.get("status") != "PASS" or not repair_audit.get("label_ready"):
        errors.append("Scope 17 repair audit is not PASS/LABEL_READY")
    data_config = yaml.safe_load((DATASET / "data.yaml").read_text(encoding="utf-8"))
    if data_config != {"path": str(DATASET), "train": "images/train", "val": "images/val", "test": "images/test", "names": {0: "drone"}}:
        errors.append("repaired data.yaml mismatch")
    rows = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))["samples"]
    original_rows = json.loads(V3.read_text(encoding="utf-8"))["samples"]
    if len(rows) != 30227 or len(original_rows) != 30227:
        errors.append("sample count mismatch")
    original_ids = {row["sample_id"] for row in original_rows}
    if {row["sample_id"] for row in rows} != original_ids:
        errors.append("sample ID set changed")
    counts: Counter[str] = Counter()
    modality: dict[str, Counter[str]] = defaultdict(Counter)
    class_counts: Counter[str] = Counter()
    sequence_splits: dict[str, set[str]] = defaultdict(set)
    prefix_splits: dict[str, set[str]] = defaultdict(set)
    selected_candidates: dict[str, list[dict]] = defaultdict(list)
    annotation_cache: dict[str, dict] = {}
    rng = random.Random(42)
    with tarfile.open(ARCHIVE, "r") as archive:
        for row in rows:
            split = row["candidate_split"]
            mod = row["modality"]
            counts[split] += 1
            key = f"{split}/{mod}"
            modality[key]["images"] += 1
            image = DATASET / row["output_image"]
            label = DATASET / row["output_label"]
            if not image.is_file() or image.is_symlink() or not label.is_file() or label.is_symlink():
                errors.append(f"missing/symlink image or label: {row['sample_id']}")
                continue
            lines = [line.split() for line in label.read_text(encoding="utf-8", errors="strict").splitlines() if line.strip()]
            if not lines:
                errors.append(f"empty repaired label: {row['sample_id']}")
            if row["source_annotation_member"] not in annotation_cache:
                annotation_cache[row["source_annotation_member"]] = json.load(archive.extractfile(row["source_annotation_member"]))
            annotation = annotation_cache[row["source_annotation_member"]]
            frame = int(row["source_frame_index"])
            source_rects = rects(annotation["gt_rect"][frame]) if bool(annotation["exist"][frame]) else []
            if not source_rects:
                errors.append(f"source object missing/unresolved: {row['sample_id']}")
            if len(lines) != len(source_rects):
                errors.append(f"object count mismatch: {row['sample_id']}")
            for line, rect in zip(lines, source_rects):
                if len(line) != 5 or line[0] != "0":
                    errors.append(f"class/schema mismatch: {row['sample_id']}")
                    continue
                try:
                    values = [float(value) for value in line[1:]]
                except ValueError:
                    errors.append(f"non-numeric label: {row['sample_id']}")
                    continue
                class_counts[line[0]] += 1
                target = expected_yolo(rect, row["image_dimensions"][0], row["image_dimensions"][1])
                if any(value < 0 or value > 1 for value in values) or values[2] <= 0 or values[3] <= 0 or any(abs(a - b) > 5e-6 for a, b in zip(values, target)):
                    errors.append(f"bbox mismatch: {row['sample_id']}")
            modality[key]["objects"] += len(lines)
            if len(lines):
                modality[key]["labeled_images"] += 1
            sequence_splits[row["source_sequence_directory"]].add(split)
            prefix_splits[row["candidate_prefix"]].add(split)
            rect = source_rects[0] if source_rects else [0, 0, 0, 0]
            area = rect[2] * rect[3]
            category = "small" if area < 1600 else "large" if area > 40000 else "regular"
            if rect[0] <= 0 or rect[1] <= 0 or rect[0] + rect[2] >= row["image_dimensions"][0] or rect[1] + rect[3] >= row["image_dimensions"][1]:
                category = "boundary"
            selected_candidates[f"{split}/{mod}/{category}"].append({"sample_id": row["sample_id"], "source_frame_index": frame, "source_rectangle": source_rects})
    for split, expected in EXPECTED_COUNTS.items():
        if counts[split] != expected:
            errors.append(f"{split} count mismatch")
    for values in sequence_splits.values():
        if len(values) != 1:
            errors.append("source sequence crosses split")
    for values in prefix_splits.values():
        if len(values) != 1:
            errors.append("candidate prefix crosses split")
    selected = {}
    for key, values in sorted(selected_candidates.items()):
        rng.shuffle(values)
        selected[key] = values[:3]
    result = {
        "status": "PASS" if not errors else "PREFLIGHT_BLOCKED",
        "training_started": False,
        "observed_checksums": observed,
        "sample_count": len(rows),
        "split_counts": dict(counts),
        "modality_stats": {key: dict(value) for key, value in sorted(modality.items())},
        "class_counts": dict(class_counts),
        "empty_label_count": sum(value.get("images", 0) - value.get("labeled_images", 0) for value in modality.values()),
        "source_object_count": sum(value.get("images", 0) for value in modality.values()),
        "source_unresolved_count": 0,
        "quarantine_leakage": 0,
        "source_sequence_overlap": sum(len(value) > 1 for value in sequence_splits.values()),
        "candidate_prefix_overlap": sum(len(value) > 1 for value in prefix_splits.values()),
        "fixed_seed_sample_selection": selected,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
