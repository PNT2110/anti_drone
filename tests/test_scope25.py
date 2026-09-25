"""Scope 25 freeze guards: verify inputs and preserve the blocked freeze state."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope25"


def read(name: str):
    return json.loads((RUNTIME / name).read_text())


def test_scope25_exact_candidate_and_hashes():
    audit = read("input_audit.json")
    assert audit["status"] == "INPUTS_VERIFIED"
    assert audit["candidate_id"] == "scope18-yolov8n-480:ncnn"
    assert audit["best_pt"]["sha256"] == "359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e"
    assert audit["ncnn"]["param_sha256"] == "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
    assert audit["ncnn"]["bin_sha256"] == "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def test_scope25_contract_and_train_only_boundary():
    audit = read("input_audit.json")
    assert audit["benchmark_manifest"].endswith(".runtime/scope19/benchmark_input_manifest.json")
    assert audit["test_accessed"] is False
    assert audit["frozen_val"] == {"map50_95": 0.62836, "recall": 0.98689}
    assert audit["calibration_int8_status"] == "PTQ_INT8_PATHS_EXHAUSTED_FOR_CURRENT_SCOPE"


def test_scope25_pi_gate_and_freeze_manifest_pass():
    pi = read("pi_reproduction.json")
    status = read("freeze_status.json")
    smoke = read("pi_smoke_result.json")
    freeze = read("scope25_freeze_manifest.json")
    assert pi["status"] == "PI_REPRODUCTION_PASS"
    assert pi["transfer_performed"] is True
    assert pi["smoke_performed"] is True
    assert smoke["status"] == "SMOKE_PASS"
    assert len(smoke["images"]) == 8
    assert all(row["parity"]["status"] == "PARITY_PASS" for row in smoke["images"])
    assert status["status"] == "FP32_NCNN_CANDIDATE_FROZEN"
    assert status["package_created"] is True
    assert status["freeze_manifest_created"] is True
    assert freeze["status"] == "FP32_NCNN_CANDIDATE_FROZEN"
    assert status["test_accessed"] is False
    assert (ROOT / "artifacts/production-candidate/scope25").is_dir()
    assert (RUNTIME / "scope25_freeze_manifest.json").is_file()


def test_scope25_package_and_tracker_configs_remain_present():
    audit = read("input_audit.json")
    assert Path(audit["best_pt"]["path"]).is_file()
    source_dir = Path(audit["ncnn"]["source_dir"])
    assert (source_dir / "model.ncnn.param").is_file()
    assert (source_dir / "model.ncnn.bin").is_file()
    package = ROOT / "artifacts/production-candidate/scope25"
    assert (package / "model.ncnn.param").is_file()
    assert (package / "model.ncnn.bin").is_file()
    assert (package / "SHA256SUMS").is_file()
    for name in ("bytetrack_legacy.yaml", "bytetrack_motion.yaml", "bytetrack_motion_adaptive.yaml"):
        assert (ROOT / "configs/trackers" / name).is_file()
