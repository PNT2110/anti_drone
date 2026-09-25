from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope21"


def test_scope21_accounts_exactly_ten_parity_pass_candidates():
    audit = json.loads((RUNTIME / "input_audit.json").read_text())
    assert audit["status"] == "PASS"
    assert audit["candidate_count"] == 10
    assert all(row["scope20_parity"] == "PARITY_PASS" for row in audit["candidates"])
    assert not any(row["backend"] == "ncnn" and "yolo26" in row["run_id"] for row in audit["candidates"])


def test_scope21_keeps_test_locked_and_benchmark_train_only():
    audit = json.loads((RUNTIME / "input_audit.json").read_text())
    assert audit["baseline"]["test_accessed"] is False
    assert audit["baseline"]["v3_test_locked"] is True
    assert audit["baseline"]["benchmark_split"] == "train"
    assert audit["baseline"]["benchmark_test_accessed"] is False


def test_scope21_does_not_claim_pi_measurements_or_freeze():
    results = json.loads((RUNTIME / "benchmark_results.json").read_text())
    selection = json.loads((RUNTIME / "selection_evidence.json").read_text())
    assert results["status"] == "PASS"
    assert len(results["results"]) == 10
    assert all(row["status"] == "PI_BENCHMARK_PASS" for row in results["results"])
    assert selection["production_freeze"] is False
