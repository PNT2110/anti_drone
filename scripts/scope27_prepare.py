#!/usr/bin/env python3
"""Audit Scope 27 inputs without opening V3 TEST or changing the detector."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope27"
SEQ = ROOT / "data/tracking_eval/sequence_001"
VIDEO = SEQ / "source/V_DRONE_001.mp4"
FREEZE = ROOT / ".runtime/scope25/scope25_freeze_manifest.json"
HEADLINE = ROOT / ".runtime/scope26/headline_result.json"
EXPECTED_FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
EXPECTED_HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
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
    freeze_hash = sha256(FREEZE)
    headline_hash = sha256(HEADLINE)
    if freeze_hash != EXPECTED_FREEZE:
        raise SystemExit("FREEZE_MANIFEST_MISMATCH")
    if headline_hash != EXPECTED_HEADLINE:
        raise SystemExit("SCOPE26_HEADLINE_MISMATCH")
    freeze = json.loads(FREEZE.read_text())
    headline = json.loads(HEADLINE.read_text())
    if freeze.get("status") != "FP32_NCNN_CANDIDATE_FROZEN" or headline.get("status") != "FINAL_TEST_COMPLETE":
        raise SystemExit("BASELINE_STATUS_MISMATCH")
    package = ROOT / "artifacts/production-candidate/scope25"
    sums = (package / "SHA256SUMS").read_text().splitlines()
    package_hashes = {}
    for line in sums:
        expected, name = line.split(maxsplit=1)
        actual = sha256(package / name)
        if actual != expected:
            raise SystemExit(f"PACKAGE_HASH_MISMATCH:{name}")
        package_hashes[name] = actual
    if package_hashes.get("model.ncnn.param") != EXPECTED_PARAM or package_hashes.get("model.ncnn.bin") != EXPECTED_BIN:
        raise SystemExit("DETECTOR_ARTIFACT_HASH_MISMATCH")

    manifest_rows = list(csv.DictReader((SEQ / "frame_manifest.csv").open()))
    box_rows = list(csv.DictReader((SEQ / "annotations/source_boxes.csv").open()))
    validation = json.loads((SEQ / "review/identity_review_validation.json").read_text())
    if len(manifest_rows) != 301 or len(box_rows) != 301 or validation.get("status") != "PASS":
        raise SystemExit("HALMSTAD_INPUT_BLOCKED")
    boxes = {int(row["frame_id"]): [float(row[key]) for key in ("x1", "y1", "x2", "y2")] for row in box_rows}
    sequence = []
    previous_timestamp = None
    for row in manifest_rows:
        frame_id = int(row["frame_id"])
        timestamp = float(row["timestamp"])
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise SystemExit("HALMSTAD_TIMESTAMP_NOT_MONOTONIC")
        previous_timestamp = timestamp
        if row["sequence_id"] != "halmstad_v_drone_001" or int(row["image_width"]) != 640 or int(row["image_height"]) != 512:
            raise SystemExit("HALMSTAD_SCHEMA_MISMATCH")
        sequence.append({"frame_id": frame_id, "source_frame_index": int(row["source_frame_index"]), "timestamp": timestamp, "image_width": 640, "image_height": 512, "gt_bbox": boxes[frame_id]})
    video_hash = sha256(VIDEO)
    audit = {"status": "INPUTS_VERIFIED", "freeze_manifest_sha256": freeze_hash, "scope26_headline_sha256": headline_hash, "candidate_id": freeze["candidate_id"], "detector": {"backend": "NCNN", "precision": "FP32", "imgsz": 480, "confidence": 0.25, "nms_iou": 0.70, "param_sha256": EXPECTED_PARAM, "bin_sha256": EXPECTED_BIN}, "tracker_profile_current": "bytetrack_motion_adaptive", "tracker_config_source": "configs/trackers/bytetrack_motion_adaptive.yaml", "sequence_id": "halmstad_v_drone_001", "source_video": str(VIDEO), "source_video_sha256": video_hash, "frames": 301, "fps": 30.0, "frame_size": [640, 512], "identity_validation": validation["status"], "diagnostic_only": True, "v3_test_used_for_tuning": False, "physical_actuator_enabled": False}
    RUNTIME.mkdir(parents=True, exist_ok=True)
    write_json(RUNTIME / "input_audit.json", audit)
    write_json(RUNTIME / "sequence_manifest.json", sequence)
    print(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
