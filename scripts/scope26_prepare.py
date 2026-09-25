#!/usr/bin/env python3
"""Lock Scope 26 inputs and record the first authorized TEST-open event.

This preparation phase reads manifests and labels only. It does not decode any
TEST image; the first image decode occurs in the Pi NCNN runner after the event
has been written.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope26"
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
PACKAGE = ROOT / "artifacts/production-candidate/scope25"
FREEZE = ROOT / ".runtime/scope25/scope25_freeze_manifest.json"
EXPECTED_FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
EXPECTED_DATASET = "bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45"
EXPECTED_SPLIT = "c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1"
EXPECTED_BEST = "359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e"
EXPECTED_PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
EXPECTED_BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if (RUNTIME / "test_open_event.json").exists():
        raise SystemExit("TEST_OPEN_EVENT_EXISTS: Scope 26 is already permanently opened")
    freeze_hash = sha256(FREEZE)
    if freeze_hash != EXPECTED_FREEZE:
        raise SystemExit(f"FREEZE_MANIFEST_MISMATCH: {freeze_hash}")
    freeze = json.loads(FREEZE.read_text())
    if freeze.get("status") != "FP32_NCNN_CANDIDATE_FROZEN" or freeze.get("candidate_id") != "scope18-yolov8n-480:ncnn":
        raise SystemExit("FREEZE_MANIFEST_MISMATCH: status or candidate")

    sums = (PACKAGE / "SHA256SUMS").read_text().splitlines()
    package_hashes = {}
    for line in sums:
        digest, name = line.split(maxsplit=1)
        path = PACKAGE / name
        if not path.is_file() or sha256(path) != digest:
            raise SystemExit(f"PACKAGE_HASH_MISMATCH: {name}")
        package_hashes[name] = digest
    if package_hashes.get("model.ncnn.param") != EXPECTED_PARAM or package_hashes.get("model.ncnn.bin") != EXPECTED_BIN:
        raise SystemExit("PACKAGE_HASH_MISMATCH: NCNN pair")
    model_manifest = json.loads((PACKAGE / "model_manifest.json").read_text())
    if model_manifest.get("source_best_pt_sha256") != EXPECTED_BEST:
        raise SystemExit("PACKAGE_HASH_MISMATCH: source checkpoint")

    dataset_manifest = DATASET / "manifest.json"
    split_registry = DATASET / "split_registry.json"
    if sha256(dataset_manifest) != EXPECTED_DATASET:
        raise SystemExit("DATASET_MANIFEST_MISMATCH")
    if sha256(split_registry) != EXPECTED_SPLIT:
        raise SystemExit("SPLIT_REGISTRY_MISMATCH")
    registry = json.loads(split_registry.read_text())
    expected_counts = {"train": 12142, "val": 8237, "test": 9848}
    if registry.get("actual_counts") != expected_counts or registry.get("session_disjoint") != "UNVERIFIED":
        raise SystemExit(f"SPLIT_REGISTRY_MISMATCH: {registry.get('actual_counts')}")

    samples = json.loads(dataset_manifest.read_text())["samples"]
    test_samples = [sample for sample in samples if sample.get("candidate_split") == "test"]
    if len(test_samples) != 9848:
        raise SystemExit(f"TEST_COUNT_MISMATCH: {len(test_samples)}")
    seen = set()
    records = []
    label_objects = 0
    modality_counts = {"visible": 0, "infrared": 0}
    for sample in test_samples:
        sample_id = sample["sample_id"]
        image_rel = sample["output_image"]
        label_rel = sample["output_label"]
        if sample_id in seen or image_rel in seen:
            raise SystemExit(f"DUPLICATE_TEST_SAMPLE: {sample_id}")
        seen.add(sample_id)
        seen.add(image_rel)
        image_path = DATASET / image_rel
        label_path = DATASET / label_rel
        if not image_path.is_file() or not label_path.is_file():
            raise SystemExit(f"MISSING_TEST_MEMBER: {image_rel} / {label_rel}")
        width, height = sample["image_dimensions"]
        gt_boxes = []
        for line in label_path.read_text().splitlines():
            fields = line.split()
            if len(fields) != 5:
                raise SystemExit(f"INVALID_TEST_LABEL: {label_rel}")
            class_id, xc, yc, bw, bh = map(float, fields)
            if int(class_id) != 0:
                raise SystemExit(f"UNEXPECTED_CLASS: {label_rel}")
            gt_boxes.append([(xc - bw / 2) * width, (yc - bh / 2) * height, (xc + bw / 2) * width, (yc + bh / 2) * height])
        modality = sample.get("modality", "unknown")
        modality_counts[modality] = modality_counts.get(modality, 0) + 1
        label_objects += len(gt_boxes)
        records.append({
            "sample_id": sample_id,
            "image_rel": image_rel,
            "label_rel": label_rel,
            "modality": modality,
            "source_sequence": sample.get("source_sequence_directory"),
            "source_frame_index": sample.get("source_frame_index"),
            "source_video_member": sample.get("source_video_member"),
            "image_dimensions": [width, height],
            "gt_boxes": gt_boxes,
        })

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "freeze_manifest_sha256": freeze_hash,
        "candidate_id": freeze["candidate_id"],
        "source_best_pt_sha256": EXPECTED_BEST,
        "param_sha256": EXPECTED_PARAM,
        "bin_sha256": EXPECTED_BIN,
        "dataset_manifest_sha256": EXPECTED_DATASET,
        "split_registry_sha256": EXPECTED_SPLIT,
        "confidence": 0.25,
        "nms_iou": 0.70,
        "imgsz": 480,
        "backend": "NCNN",
        "precision": "FP32",
        "runtime_version": model_manifest["backend_version"],
        "test_split": "test",
        "expected_test_images": 9848,
        "test_open_authorized": True,
    }
    write_json(RUNTIME / "test_open_event.json", event)
    with (RUNTIME / "test_manifest.jsonl").open("w") as handle:
        for record in records:
            handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
    audit = {
        "status": "TEST_OPENED",
        "freeze_manifest_sha256": freeze_hash,
        "candidate_id": freeze["candidate_id"],
        "dataset_manifest_sha256": EXPECTED_DATASET,
        "split_registry_sha256": EXPECTED_SPLIT,
        "expected_counts": expected_counts,
        "test_expected": len(records),
        "test_manifest_records": len(records),
        "test_label_objects": label_objects,
        "modality_counts": modality_counts,
        "skipped": 0,
        "test_accessed": True,
        "preprocess_contract": json.loads((PACKAGE / "preprocess_contract.json").read_text()),
        "postprocess_contract": json.loads((PACKAGE / "postprocess_contract.json").read_text()),
    }
    write_json(RUNTIME / "input_audit.json", audit)
    print(json.dumps({"status": audit["status"], "event": event, "test_records": len(records), "modality_counts": modality_counts, "label_objects": label_objects}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
