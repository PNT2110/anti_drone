#!/usr/bin/env python3
"""Verify immutable Scope 25 inputs and prepare the smoke reference."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope25"
BEST = ROOT / "artifacts/experiments/scope18-v3-labelrepair/scope18-yolov8n-480/attempt-batch16/weights/best.pt"
NCNN = ROOT / "artifacts/exports/scope19/scope18-yolov8n-480/float32/ncnn/model_ncnn_model"
EXPECTED = {
    "best.pt": "359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e",
    "model.ncnn.param": "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5",
    "model.ncnn.bin": "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    actual = {"best.pt": sha256(BEST), "model.ncnn.param": sha256(NCNN / "model.ncnn.param"), "model.ncnn.bin": sha256(NCNN / "model.ncnn.bin")}
    if actual != EXPECTED:
        raise SystemExit(json.dumps({"status": "BLOCKED_FREEZE_INPUT_CHANGED", "expected": EXPECTED, "actual": actual}, indent=2))
    scope21_audit = json.loads((ROOT / ".runtime/scope21/input_audit.json").read_text())
    scope21_summary = json.loads((ROOT / ".runtime/scope21/scope21_summary.json").read_text())
    selected_audit = next(x for x in scope21_audit["candidates"] if x["candidate_id"] == "scope18-yolov8n-480:ncnn")
    selected_result = next(x for x in scope21_summary["results"] if x["candidate_id"] == "scope18-yolov8n-480:ncnn")
    if selected_audit["scope20_parity"] != "PARITY_PASS" or selected_result["status"] != "PI_BENCHMARK_PASS":
        raise SystemExit("BLOCKED: historical Scope 20/21 evidence is not PASS")
    benchmark = json.loads((ROOT / ".runtime/scope19/benchmark_input_manifest.json").read_text())
    if benchmark.get("split") != "train" or benchmark.get("test_accessed") is not False or len(benchmark["paths"]) != 8:
        raise SystemExit("BLOCKED: fixed benchmark manifest is not the locked 8-image TRAIN set")
    reference = {"status": "PASS", "split": "train", "test_accessed": False, "image_count": 8, "records": [x for x in json.loads((ROOT / ".runtime/scope21/host_reference.json").read_text())["records"] if x["run_id"] == "scope18-yolov8n-480"]}
    (RUNTIME / "host_reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    input_audit = {
        "status": "INPUTS_VERIFIED",
        "candidate_id": "scope18-yolov8n-480:ncnn",
        "best_pt": {"path": str(BEST), "sha256": actual["best.pt"], "expected": EXPECTED["best.pt"]},
        "ncnn": {"source_dir": str(NCNN), "param_sha256": actual["model.ncnn.param"], "bin_sha256": actual["model.ncnn.bin"], "param_bytes": (NCNN / "model.ncnn.param").stat().st_size, "bin_bytes": (NCNN / "model.ncnn.bin").stat().st_size},
        "dataset_manifest_sha256": "bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45",
        "split_registry_sha256": "c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1",
        "calibration_int8_status": "PTQ_INT8_PATHS_EXHAUSTED_FOR_CURRENT_SCOPE",
        "scope20_parity": selected_audit["scope20_parity"],
        "scope21_pi_status": selected_result["status"],
        "scope21_pi_runtime": selected_result["runtime"],
        "scope21_pi_fps": 22.493,
        "scope21_pi_model_bytes": selected_result["model_bytes"],
        "frozen_val": {"map50_95": 0.62836, "recall": 0.98689},
        "benchmark_manifest": str(ROOT / ".runtime/scope19/benchmark_input_manifest.json"),
        "test_accessed": False,
    }
    (RUNTIME / "input_audit.json").write_text(json.dumps(input_audit, indent=2) + "\n")
    print(json.dumps(input_audit, indent=2))


if __name__ == "__main__":
    main()
