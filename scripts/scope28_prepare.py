#!/usr/bin/env python3
"""Scope 28 baseline audit and direct Scope 27 contract diagnosis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope28"
PACKAGE = ROOT / "artifacts/production-candidate/scope25"
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
    freeze = ROOT / ".runtime/scope25/scope25_freeze_manifest.json"
    headline = ROOT / ".runtime/scope26/headline_result.json"
    if sha256(freeze) != EXPECTED_FREEZE:
        raise SystemExit("FREEZE_MANIFEST_MISMATCH")
    if sha256(headline) != EXPECTED_HEADLINE:
        raise SystemExit("SCOPE26_HEADLINE_MISMATCH")
    package_hashes = {}
    for line in (PACKAGE / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        actual = sha256(PACKAGE / name)
        if actual != expected:
            raise SystemExit(f"PACKAGE_HASH_MISMATCH:{name}")
        package_hashes[name] = actual
    if package_hashes.get("model.ncnn.param") != EXPECTED_PARAM or package_hashes.get("model.ncnn.bin") != EXPECTED_BIN:
        raise SystemExit("DETECTOR_ARTIFACT_HASH_MISMATCH")

    scope27 = json.loads((ROOT / ".runtime/scope27/input_audit.json").read_text())
    if scope27["tracker_profile_current"] != "bytetrack_motion_adaptive":
        raise SystemExit("TRACKER_PROFILE_MISMATCH")
    tracker_config = json.loads((ROOT / ".runtime/scope27/dryrun_config.json").read_text())["tracker_config"]
    source = (ROOT / "scripts/scope27_pi_dryrun.py").read_text()
    decoder = (ROOT / "scripts/scope21_pi_runner.py").read_text()
    tracking = (ROOT / "src/anti_drone/tracking/bytetrack.py").read_text()
    discard_evidence = {
        "scope27_runner_calls_scope21_decode": "decode(raw, gain, pad, frame.shape[:2])" in source,
        "scope21_public_confidence_constant": "CONF = 0.25" in decoder,
        "scope21_decode_filters_below_public_threshold": "if conf < CONF" in decoder,
        "scope27_passes_only_decoder_return_to_tracker": "tracker.update(detections" in source,
        "bytetrack_low_threshold_exists_but_receives_no_prethreshold_rows": "track_low_thresh" in tracking,
    }
    actual_gap = all(discard_evidence.values())
    if not actual_gap:
        diagnosis_status = "CONTRACT_ALREADY_SATISFIED"
    else:
        diagnosis_status = "CONTRACT_GAP_CONFIDENCE_FLOOR"
    audit = {
        "status": "INPUTS_VERIFIED",
        "scope28_status": diagnosis_status,
        "freeze_manifest_sha256": sha256(freeze),
        "scope26_headline_sha256": sha256(headline),
        "candidate_id": "scope18-yolov8n-480:ncnn",
        "detector": {"backend": "NCNN", "precision": "FP32", "imgsz": 480, "confidence": 0.25, "nms_iou": 0.70, "param_sha256": EXPECTED_PARAM, "bin_sha256": EXPECTED_BIN},
        "tracker_profile": "bytetrack_motion_adaptive",
        "tracker_config": tracker_config,
        "halmstad_frames": 301,
        "halmstad_video_sha256": scope27["source_video_sha256"],
        "v3_test_used_for_tuning": False,
        "webcam_used": False,
        "physical_actuation_enabled": False,
        "production_package_modified": False,
    }
    diagnosis = {
        "status": diagnosis_status,
        "question": "Does Scope 27 discard 0.10 <= confidence < 0.25 before ByteTrack.update?",
        "answer": "YES" if actual_gap else "NO",
        "evidence": discard_evidence,
        "references": {
            "scope27_runner": "scripts/scope27_pi_dryrun.py",
            "scope21_decoder": "scripts/scope21_pi_runner.py",
            "tracker": "src/anti_drone/tracking/bytetrack.py",
        },
        "explanation": "Scope 27 calls the Scope 21 decoder, whose CONF=0.25 filter runs before ByteTrack.update; the existing tracker low threshold 0.10 therefore cannot receive 0.10-<0.25 observations." if actual_gap else "The low stream is already passed to the tracker.",
        "required_action": "Implement an adapter-side single-inference, single-NMS dual stream." if actual_gap else "No code change is required.",
    }
    write_json(RUNTIME / "input_audit.json", audit)
    write_json(RUNTIME / "contract_diagnosis.json", diagnosis)
    print(json.dumps(diagnosis, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
