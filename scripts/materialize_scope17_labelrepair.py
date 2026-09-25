"""Materialize a separate V3 label-repair candidate from source annotations."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import time
from collections import Counter
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATASET = ROOT / "data/processed/drone-single-class-v3-candidate"
OUTPUT = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
MANIFEST = SOURCE_DATASET / "manifest.json"
REGISTRY = SOURCE_DATASET / "split_registry.json"
ROOT_AUDIT = ROOT / ".runtime/scope17/root_cause_audit.json"
ARCHIVE = ROOT / "data/import_data_rar/Anti-UAV300.tar"
EXPECTED_MANIFEST = "b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc"
EXPECTED_REGISTRY = "57ffb56effd35ad65aad9d163e586ebd8c9f9f1f19c93a86d5fd7619d72cff3d"
EXPECTED_COUNTS = {"train": 12142, "val": 8237, "test": 9848}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def rects_for(value: object) -> list[list[float]]:
    if isinstance(value, list) and len(value) == 4 and all(isinstance(item, (int, float)) for item in value):
        return [[float(item) for item in value]]
    if isinstance(value, list) and all(isinstance(item, list) and len(item) == 4 for item in value):
        return [[float(item) for item in rect] for rect in value]
    return []


def convert_rect(rect: list[float], width: int, height: int) -> list[float]:
    x, y, w, h = rect
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
        raise RuntimeError(f"BLOCKED: source rectangle outside bounds: {rect} for {width}x{height}")
    return [(x + w / 2) / width, (y + h / 2) / height, w / width, h / height]


def label_text(rects: list[list[float]], width: int, height: int) -> str:
    return "".join("0 " + " ".join(f"{value:.8f}" for value in convert_rect(rect, width, height)) + "\n" for rect in rects)


def main() -> int:
    if sha256(MANIFEST) != EXPECTED_MANIFEST or sha256(REGISTRY) != EXPECTED_REGISTRY:
        raise RuntimeError("BLOCKED: V3 candidate baseline checksum changed")
    root_audit = json.loads(ROOT_AUDIT.read_text(encoding="utf-8"))
    if root_audit.get("status") != "PASS" or not root_audit.get("repair_allowed"):
        raise RuntimeError("BLOCKED: Scope 17 root-cause/coordinate audit is not PASS")
    if OUTPUT.exists():
        raise RuntimeError(f"BLOCKED: refusing to overwrite existing repair candidate: {OUTPUT}")
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))["samples"]
    estimated_bytes = sum((SOURCE_DATASET / row["output_image"]).stat().st_size for row in rows)
    free_bytes = shutil.disk_usage(OUTPUT.parent).free
    required = int(estimated_bytes * 1.10) + 256 * 1024 * 1024
    if free_bytes < required:
        raise RuntimeError(f"BLOCKED: insufficient free space: free={free_bytes}, required={required}")
    temp = OUTPUT.with_name(OUTPUT.name + f".building-{os.getpid()}")
    if temp.exists():
        raise RuntimeError(f"BLOCKED: stale temporary output exists: {temp}")

    started = time.time()
    counters: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    modality_counts: Counter[str] = Counter()
    materialized = []
    annotation_cache: dict[str, dict] = {}
    seen = set()
    try:
        for split in ("train", "val", "test"):
            (temp / "images" / split).mkdir(parents=True, exist_ok=True)
            (temp / "labels" / split).mkdir(parents=True, exist_ok=True)
        with tarfile.open(ARCHIVE, "r") as archive:
            for position, row in enumerate(rows, 1):
                sample_id = row["sample_id"]
                split = row["candidate_split"]
                source_image = SOURCE_DATASET / row["output_image"]
                source_label = SOURCE_DATASET / row["output_label"]
                if not source_image.is_file() or source_image.is_symlink():
                    raise RuntimeError(f"BLOCKED: source candidate image missing/symlink: {source_image}")
                image = cv2.imread(str(source_image), cv2.IMREAD_UNCHANGED)
                if image is None:
                    raise RuntimeError(f"BLOCKED: cannot decode candidate image: {source_image}")
                height, width = image.shape[:2]
                member = row["source_annotation_member"]
                if member not in annotation_cache:
                    annotation_cache[member] = json.load(archive.extractfile(member))
                annotation = annotation_cache[member]
                frame = int(row["source_frame_index"])
                exist = annotation["exist"][frame]
                source_rects = rects_for(annotation["gt_rect"][frame]) if bool(exist) else []
                if bool(exist) and not source_rects:
                    raise RuntimeError(f"BLOCKED: exist=1 with unusable source rectangle: {sample_id}")
                if not bool(exist) and source_rects:
                    raise RuntimeError(f"BLOCKED: exist=0 with source rectangle: {sample_id}")
                text = label_text(source_rects, width, height)
                output_image = temp / row["output_image"]
                output_label = temp / row["output_label"]
                key = (split, row["output_image"], row["output_label"])
                if key in seen:
                    raise RuntimeError(f"BLOCKED: duplicate output key: {key}")
                seen.add(key)
                output_image.parent.mkdir(parents=True, exist_ok=True)
                output_label.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_image, output_image)
                output_label.write_text(text, encoding="utf-8")
                if output_image.is_symlink() or output_label.is_symlink():
                    raise RuntimeError(f"BLOCKED: symlink output: {sample_id}")
                output_hash = sha256(output_image)
                if output_hash != row["image_hash"]:
                    raise RuntimeError(f"BLOCKED: repaired candidate image hash changed: {sample_id}")
                original_text = source_label.read_text(encoding="utf-8", errors="strict") if source_label.is_file() else ""
                if original_text == text:
                    status = "KEPT_SOURCE_EQUIVALENT"
                    counters["kept_unchanged"] += 1
                else:
                    status = "REPAIRED_FROM_SOURCE_ANNOTATION"
                    counters["created_or_repaired"] += 1
                if source_rects:
                    counters["source_object"] += 1
                else:
                    counters["source_confirmed_negative"] += 1
                split_counts[split] += 1
                modality_counts[row["modality"]] += 1
                materialized.append({
                    "sample_id": sample_id,
                    "candidate_split": split,
                    "source_image_hash": row["image_hash"],
                    "source_image": row["output_image"],
                    "source_archive": "Anti-UAV300.tar",
                    "source_video_member": row["source_video_member"],
                    "source_annotation_member": member,
                    "source_frame_index": frame,
                    "modality": row["modality"],
                    "source_rectangle_xywh_pixels": source_rects,
                    "image_dimensions": [width, height],
                    "coordinate_rule": "source gt_rect xywh pixels; direct image coordinates; YOLO xc=(x+w/2)/W, yc=(y+h/2)/H, w/W, h/H; 8 decimal places; no resize/crop/clip",
                    "original_v3_label_sha256": sha256(source_label),
                    "output_image": row["output_image"],
                    "output_label": row["output_label"],
                    "output_image_sha256": output_hash,
                    "output_label_sha256": sha256(output_label),
                    "repair_status": status,
                    "repair_reason": "source annotation is authoritative; existing V3 label was empty or did not match source rectangle" if status.startswith("REPAIRED") else "existing V3 label byte-equivalent to source conversion",
                    "assignment_status": "ASSIGNED",
                    "candidate_prefix": row["candidate_prefix"],
                    "source_sequence_directory": row["source_sequence_directory"],
                    "original_source_partition": row["original_source_partition"],
                    "provenance_status": "CONFIRMED_SOURCE_SEQUENCE_ARCHIVE_MEMBER; SESSION_DISJOINT_UNVERIFIED",
                })
                if position % 2000 == 0:
                    print(f"repaired {position}/{len(rows)}", flush=True)
        metadata = {
            "dataset_id": "drone-single-class-v3-labelrepair-candidate",
            "dataset_version": "scope17-source-annotation-repair-v1",
            "source_v3_manifest_sha256": EXPECTED_MANIFEST,
            "source_v3_split_registry_sha256": EXPECTED_REGISTRY,
            "scope17_root_cause_audit_sha256": sha256(ROOT_AUDIT),
            "source_archive": "data/import_data_rar/Anti-UAV300.tar",
            "source_archive_sha256_reference": "c8af3934b7b84c21f1ecfda4723c11b186a6c7182c1ece2b629ebc2035fa6e2f",
            "sample_count": len(materialized),
            "split_counts": dict(split_counts),
            "quarantine_excluded": {"samples": 6505, "groups": 4172},
            "session_disjoint": "UNVERIFIED",
            "materialization": "copy2 of V3 candidate images; new labels from archive source annotation; no resize/crop/source mutation",
            "data_yaml_created": False,
            "created_at_unix": started,
        }
        write_json(temp / "manifest.json", {"metadata": metadata, "samples": materialized})
        write_json(temp / "split_registry.json", {"dataset_id": metadata["dataset_id"], "source_v3_manifest_sha256": EXPECTED_MANIFEST, "actual_counts": dict(split_counts), "sample_count": len(materialized), "source_sequence_overlap": 0, "candidate_prefix_overlap": 0, "session_disjoint": "UNVERIFIED", "production_status": "CANDIDATE_ONLY"})
        write_json(temp / "repair_materialization_report.json", {"status": "PASS", "sample_count": len(materialized), "split_counts": dict(split_counts), "modality_counts": dict(modality_counts), "repair_counts": dict(counters), "estimated_source_image_bytes": estimated_bytes, "free_bytes_before": free_bytes, "safety_required_bytes": required, "elapsed_seconds": time.time() - started, "data_yaml_created": False})
        os.replace(temp, OUTPUT)
    except Exception:
        raise
    print(json.dumps({"output": str(OUTPUT), "sample_count": len(materialized), "split_counts": dict(split_counts), "repair_counts": dict(counters)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
