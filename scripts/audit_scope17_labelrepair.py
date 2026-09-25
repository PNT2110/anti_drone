"""Independent direct-disk audit for the Scope 17 repaired-label candidate."""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/drone-single-class-v3-candidate"
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
V3_MANIFEST = SOURCE / "manifest.json"
V2_MANIFEST = ROOT / "data/processed/drone-single-class-v2/manifest.json"
ARCHIVE = ROOT / "data/import_data_rar/Anti-UAV300.tar"
OUT = ROOT / ".runtime/scope17/label_repair_audit.json"
DATASET_OUT = DATASET / "label_repair_audit.json"
EXPECTED = {"train": 12142, "val": 8237, "test": 9848}
EXPECTED_V3 = "b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc"
EXPECTED_V3_REGISTRY = "57ffb56effd35ad65aad9d163e586ebd8c9f9f1f19c93a86d5fd7619d72cff3d"
RGBT_RE = re.compile(r"^RGBT_(train|val|test)_(\d{8})_(\d{6})_(\d+)_(\d+)_(visible|infrared)_(\d+)\.jpg$")


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
    if not DATASET.is_dir():
        raise RuntimeError(f"BLOCKED: repair candidate missing: {DATASET}")
    errors: list[str] = []
    if sha256(V3_MANIFEST) != EXPECTED_V3 or sha256(SOURCE / "split_registry.json") != EXPECTED_V3_REGISTRY:
        errors.append("source V3 checksum changed")
    source_manifest = json.loads(V3_MANIFEST.read_text(encoding="utf-8"))
    source_rows = {row["sample_id"]: row for row in source_manifest["samples"]}
    v2 = json.loads(V2_MANIFEST.read_text(encoding="utf-8"))
    v2_assignment = {(row["source"], row["image"]): row.get("assignment_status") for row in v2["samples"]}
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    rows = manifest["samples"]
    if len(rows) != 30227:
        errors.append(f"repair manifest count {len(rows)} != 30227")
    counts: Counter[str] = Counter()
    modality: dict[str, Counter[str]] = defaultdict(Counter)
    repair_status: Counter[str] = Counter()
    sequence_splits: dict[str, set[str]] = defaultdict(set)
    prefix_splits: dict[str, set[str]] = defaultdict(set)
    sample_ids: set[str] = set()
    output_ids: set[tuple[str, str, str]] = set()
    object_total = 0
    source_objects = 0
    source_negatives = 0
    after_labeled = 0
    unresolved = 0
    before_labeled = 0
    before_empty = 0
    label_hashes = set()
    annotation_cache: dict[str, dict] = {}

    with tarfile.open(ARCHIVE, "r") as archive:
        for row in rows:
            sample_id = row["sample_id"]
            split = row["candidate_split"]
            counts[split] += 1
            modality[modality_key := f"{split}/{row['modality']}"]["images"] += 1
            if sample_id in sample_ids:
                errors.append(f"duplicate sample id: {sample_id}")
            sample_ids.add(sample_id)
            source = source_rows.get(sample_id)
            if source is None:
                errors.append(f"source V3 sample missing: {sample_id}")
                continue
            if v2_assignment.get(("base", Path(source["source_image"]).as_posix())) != "ASSIGNED":
                errors.append(f"non-assigned/quarantine source: {sample_id}")
            output_id = (split, row["output_image"], row["output_label"])
            if output_id in output_ids:
                errors.append(f"duplicate output: {output_id}")
            output_ids.add(output_id)
            image = DATASET / row["output_image"]
            label = DATASET / row["output_label"]
            original_image = SOURCE / source["output_image"]
            original_label = SOURCE / source["output_label"]
            for path in (image, label, original_image, original_label):
                if not path.is_file() or path.is_symlink():
                    errors.append(f"missing/symlink path: {path}")
            if image.is_file() and original_image.is_file():
                if sha256(image) != sha256(original_image) or sha256(image) != row["output_image_sha256"] or sha256(image) != source["image_hash"]:
                    errors.append(f"image content/hash mismatch: {sample_id}")
            if original_label.is_file() and original_label.read_text(encoding="utf-8").strip():
                before_labeled += 1
            else:
                before_empty += 1
            if original_label.is_file() and sha256(original_label) != row["original_v3_label_sha256"]:
                errors.append(f"original label hash provenance mismatch: {sample_id}")
            if row["source_annotation_member"] not in annotation_cache:
                annotation_cache[row["source_annotation_member"]] = json.load(archive.extractfile(row["source_annotation_member"]))
            ann = annotation_cache[row["source_annotation_member"]]
            frame = int(row["source_frame_index"])
            if frame >= len(ann["exist"]) or frame >= len(ann["gt_rect"]):
                errors.append(f"annotation frame out of range: {sample_id}")
                unresolved += 1
                continue
            source_rects = rects(ann["gt_rect"][frame]) if bool(ann["exist"][frame]) else []
            if source_rects:
                source_objects += 1
                after_labeled += 1
                modality[modality_key]["source_object"] += 1
            else:
                source_negatives += 1
                modality[modality_key]["source_confirmed_negative"] += 1
            decoded = cv2.imread(str(image), cv2.IMREAD_UNCHANGED)
            if decoded is None:
                errors.append(f"cannot decode repaired image: {sample_id}")
                unresolved += 1
                continue
            height, width = decoded.shape[:2]
            if [width, height] != row["image_dimensions"]:
                errors.append(f"image dimension provenance mismatch: {sample_id}")
            lines = [line.split() for line in label.read_text(encoding="utf-8").splitlines() if line.strip()] if label.is_file() else []
            if len(lines) != len(source_rects):
                errors.append(f"object count mismatch: {sample_id}: label={len(lines)} source={len(source_rects)}")
            object_total += len(lines)
            expected = [expected_yolo(rect, width, height) for rect in source_rects]
            for line, target in zip(lines, expected):
                if len(line) != 5 or line[0] != "0":
                    errors.append(f"class/schema mismatch: {sample_id}")
                    continue
                try:
                    values = [float(value) for value in line[1:]]
                except ValueError:
                    errors.append(f"non-numeric repaired label: {sample_id}")
                    continue
                if any(value < 0 or value > 1 for value in values) or values[2] <= 0 or values[3] <= 0 or any(abs(a - b) > 5e-6 for a, b in zip(values, target)):
                    errors.append(f"coordinate mismatch: {sample_id}")
            if label.is_file():
                label_hashes.add(sha256(label))
            repair_status[row["repair_status"]] += 1
            sequence_splits[row["source_sequence_directory"]].add(split)
            prefix_splits[row["candidate_prefix"]].add(split)
            if RGBT_RE.match(Path(source["source_image"]).name) is None:
                errors.append(f"source filename mapping unresolved: {sample_id}")
    for split, expected in EXPECTED.items():
        if counts[split] != expected:
            errors.append(f"split count mismatch: {split}")
    for key, values in sequence_splits.items():
        if len(values) != 1:
            errors.append(f"sequence crosses split: {key}")
    for key, values in prefix_splits.items():
        if len(values) != 1:
            errors.append(f"prefix crosses split: {key}")
    report = {
        "status": "PASS" if not errors else "FAIL",
        "label_ready": not errors,
        "dataset": str(DATASET),
        "sample_count": len(rows),
        "split_counts": dict(counts),
        "source_object_count": source_objects,
        "source_confirmed_negative_count": source_negatives,
        "source_annotation_unresolved_count": unresolved,
        "object_count": object_total,
        "before_repair": {"labeled_images": before_labeled, "empty_images": before_empty},
        "after_repair": {"labeled_images": after_labeled, "negative_images": source_negatives},
        "modality_stats": {key: dict(value) for key, value in sorted(modality.items())},
        "repair_status_counts": dict(repair_status),
        "source_sequence_count": len(sequence_splits),
        "candidate_prefix_count": len(prefix_splits),
        "source_sequence_overlap": sum(len(value) > 1 for value in sequence_splits.values()),
        "candidate_prefix_overlap": sum(len(value) > 1 for value in prefix_splits.values()),
        "quarantine_leakage": 0 if not any("quarantine" in error for error in errors) else 1,
        "data_yaml_present_before_finalize": (DATASET / "data.yaml").is_file(),
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    DATASET_OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
