"""Scope 17 root-cause and coordinate audit for the V3 labels.

Read-only: source archive, V3 manifest/images and existing labels are compared;
no current image or label is modified.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v3-candidate"
MANIFEST = DATASET / "manifest.json"
REGISTRY = DATASET / "split_registry.json"
ARCHIVE = ROOT / "data/import_data_rar/Anti-UAV300.tar"
SCOPE13 = ROOT / ".runtime/scope13/rgbt_archive_mapping.csv"
OUT = ROOT / ".runtime/scope17/root_cause_audit.json"
SAMPLES_OUT = ROOT / ".runtime/scope17/sample_selection.json"
MISMATCH_OUT = ROOT / ".runtime/scope17/existing_label_mismatches.jsonl"
EXPECTED_MANIFEST = "b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc"
EXPECTED_REGISTRY = "57ffb56effd35ad65aad9d163e586ebd8c9f9f1f19c93a86d5fd7619d72cff3d"
RGBT_RE = re.compile(r"^RGBT_(train|val|test)_(\d{8})_(\d{6})_(\d+)_(\d+)_(visible|infrared)_(\d+)\.jpg$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_yolo(rect: list[float], width: int, height: int) -> list[float]:
    x, y, w, h = map(float, rect)
    return [(x + w / 2) / width, (y + h / 2) / height, w / width, h / height]


def read_label(path: Path) -> tuple[list[list[float]], list[str]]:
    rows: list[list[float]] = []
    errors: list[str] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="strict").splitlines(), 1):
        fields = raw.split()
        if len(fields) != 5:
            errors.append(f"line {line_no}: field_count={len(fields)}")
            continue
        try:
            values = [float(value) for value in fields]
        except ValueError:
            errors.append(f"line {line_no}: non_numeric")
            continue
        rows.append(values)
    return rows, errors


def main() -> int:
    errors: list[str] = []
    if sha256(MANIFEST) != EXPECTED_MANIFEST:
        errors.append("V3 manifest checksum mismatch")
    if sha256(REGISTRY) != EXPECTED_REGISTRY:
        errors.append("V3 split registry checksum mismatch")
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))["samples"]
    mapping = {row["image"]: row for row in csv.DictReader(SCOPE13.open(encoding="utf-8"))}
    annotation_cache: dict[str, dict] = {}
    counters: Counter[str] = Counter()
    by_split_modality: dict[str, Counter[str]] = defaultdict(Counter)
    dimensions: Counter[tuple[str, int, int]] = Counter()
    mismatch_rows: list[dict] = []
    selected: dict[str, dict] = {}
    expected_by_sample: dict[str, list[float]] = {}
    observed_by_sample: dict[str, list[list[float]]] = {}

    def select(key: str, record: dict) -> None:
        if key not in selected:
            selected[key] = record

    with tarfile.open(ARCHIVE, "r") as archive:
        for row in rows:
            sample_id = row["sample_id"]
            name = Path(row["source_image"]).name
            parsed = RGBT_RE.match(name)
            if parsed is None:
                errors.append(f"filename mapping parse failed: {sample_id}")
                continue
            source_split, _date, _clock, stream_id, sequence_id, modality, frame_text = parsed.groups()
            frame = int(frame_text)
            if frame != int(row["source_frame_index"]):
                errors.append(f"frame index mismatch: {sample_id}")
            if modality != row["modality"]:
                errors.append(f"modality mismatch: {sample_id}")
            source_map = mapping.get(row["source_image"])
            if source_map is None or source_map["source_frame_index"] != str(frame):
                errors.append(f"Scope 13 mapping mismatch: {sample_id}")
            if not row["source_annotation_member"].endswith(f"/{modality}.json") or not row["source_video_member"].endswith(f"/{modality}.mp4"):
                errors.append(f"member modality mismatch: {sample_id}")
            if row["source_annotation_member"] not in annotation_cache:
                try:
                    annotation_cache[row["source_annotation_member"]] = json.load(archive.extractfile(row["source_annotation_member"]))
                except Exception as exc:
                    errors.append(f"annotation read failed {sample_id}: {exc}")
                    continue
            annotation = annotation_cache[row["source_annotation_member"]]
            exist = annotation.get("exist", [])
            gt_rects = annotation.get("gt_rect", [])
            if frame < 0 or frame >= len(exist) or frame >= len(gt_rects):
                errors.append(f"annotation frame out of range: {sample_id}")
                counters["source_annotation_unresolved"] += 1
                continue
            rect = gt_rects[frame]
            source_positive = bool(exist[frame]) and isinstance(rect, list) and len(rect) == 4
            if not source_positive:
                counters["source_confirmed_negative"] += 1
                by_split_modality[f"{row['candidate_split']}/{modality}"]["source_confirmed_negative"] += 1
                continue
            counters["source_confirmed_object"] += 1
            by_split_modality[f"{row['candidate_split']}/{modality}"]["source_confirmed_object"] += 1
            image = cv2.imread(row["source_image"], cv2.IMREAD_UNCHANGED)
            if image is None:
                errors.append(f"image decode failed: {sample_id}")
                counters["source_annotation_unresolved"] += 1
                continue
            height, width = image.shape[:2]
            dimensions[(modality, width, height)] += 1
            x, y, w, h = map(float, rect)
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
                errors.append(f"source rectangle outside image bounds: {sample_id} rect={rect} size={width}x{height}")
                counters["source_annotation_unresolved"] += 1
                continue
            expected = expected_yolo(rect, width, height)
            expected_by_sample[sample_id] = expected
            label_path = Path(row["source_label"])
            label_rows, label_errors = read_label(label_path) if label_path.is_file() else ([], ["missing_label"])
            observed_by_sample[sample_id] = label_rows
            if label_errors:
                counters["existing_label_malformed"] += 1
            if not label_rows:
                counters["source_object_existing_label_empty"] += 1
                by_split_modality[f"{row['candidate_split']}/{modality}"]["source_object_existing_label_empty"] += 1
                mismatch_rows.append({"sample_id": sample_id, "kind": "EXISTING_LABEL_MISMATCH", "reason": "source_object_but_label_empty", "source_rect": rect, "expected_yolo": expected, "label_path": str(label_path)})
            else:
                same = len(label_rows) == 1 and label_rows[0][0] == 0 and all(abs(a - b) <= 5e-6 for a, b in zip(label_rows[0][1:], expected))
                if same:
                    counters["existing_label_exact_match"] += 1
                    by_split_modality[f"{row['candidate_split']}/{modality}"]["existing_label_exact_match"] += 1
                else:
                    counters["existing_label_mismatch"] += 1
                    by_split_modality[f"{row['candidate_split']}/{modality}"]["existing_label_mismatch"] += 1
                    mismatch_rows.append({"sample_id": sample_id, "kind": "EXISTING_LABEL_MISMATCH", "reason": "nonempty_label_differs_from_source", "source_rect": rect, "expected_yolo": expected, "observed_yolo": label_rows, "label_path": str(label_path)})

            area = w * h
            record = {"sample_id": sample_id, "split": row["candidate_split"], "modality": modality, "image": row["source_image"], "label": str(label_path), "frame": frame, "source_rect": rect, "image_size": [width, height], "expected_yolo": expected, "source_annotation_member": row["source_annotation_member"]}
            select("labeled" if label_rows else "empty", record)
            select(f"{row['candidate_split']}_{modality}_{'labeled' if label_rows else 'empty'}", record)
            if w * h < 40 * 40:
                select("small_box", record)
            if w * h > 200 * 200:
                select("large_box", record)
            if x <= 0 or y <= 0 or x + w >= width or y + h >= height:
                select("boundary_box", record)
            if source_split != row["original_source_partition"]:
                errors.append(f"original partition mismatch: {sample_id}")

    # Deterministic representative edge cases are reported even if a category
    # is absent; the source corpus has one rectangle per mapped frame, so a
    # multi-box sample is explicitly counted as unavailable.
    counters["source_multi_box_frames"] = 0
    counters["source_annotation_members"] = len(annotation_cache)
    counters["sample_count"] = len(rows)
    counters["existing_label_mismatch_total"] = len(mismatch_rows)
    pipeline = {
        "v1_builder": str(ROOT / "scripts/prepare_dataset.py"),
        "v1_builder_behavior": "base labels are passed through via link_or_empty; only my_dataset labels are normalized",
        "source_converter_reference": "/home/pnt/Desktop/antidrone/drone-rocket/scripts/prepare_anti_uav300_yolo.py",
        "source_converter_behavior": "frame_id is direct zero-based JSON index; source gt_rect is [x,y,w,h] pixels; conversion normalizes xywh and writes empty only when exist is false",
        "current_label_filename_contract": "RGBT_<split>_<date>_<time>_<stream>_<sequence>_<modality>_<frame>.txt",
        "inspected_converter_output_contract": "<sequence>__f<frame:06d>.txt",
        "root_cause": "V1 builder did not generate source labels for base RGBT rows; it passed through a pre-existing sparse label directory. The inspected source converter's output naming does not match the current RGBT label files.",
    }
    result = {
        "status": "PASS" if not errors else "ROOT_CAUSE_BLOCKED",
        "repair_allowed": not errors,
        "dataset_manifest_sha256": sha256(MANIFEST),
        "split_registry_sha256": sha256(REGISTRY),
        "sample_count": len(rows),
        "counters": dict(counters),
        "by_split_modality": {key: dict(value) for key, value in sorted(by_split_modality.items())},
        "image_dimensions": {f"{modality}:{width}x{height}": count for (modality, width, height), count in sorted(dimensions.items())},
        "coordinate_contract_candidate": {"source_format": "xywh_pixels", "index_base": "0-based", "transform": "direct source image coordinates; no resize/crop/letterbox", "normalization": "xc=(x+w/2)/W, yc=(y+h/2)/H, wn=w/W, hn=h/H", "tolerance": 5e-6, "source_rect_policy": "all mapped source rectangles are positive and in bounds; no clipping required"},
        "pipeline_evidence": pipeline,
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    SAMPLES_OUT.write_text(json.dumps({"selected": selected, "selection_policy": "one deterministic first sample per split/modality/label state; additional small/large/boundary categories when present; source multi-box count reported separately"}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    with MISMATCH_OUT.open("w", encoding="utf-8") as stream:
        for item in mismatch_rows:
            stream.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
