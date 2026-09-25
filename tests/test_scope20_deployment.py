import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope20"


def read_json(name):
    return json.loads((RUNTIME / name).read_text(encoding="utf-8"))


def test_scope20_baseline_and_checkpoint_hashes_are_immutable():
    audit = read_json("input_audit.json")
    assert audit["status"] == "PASS"
    assert audit["test_accessed"] is False
    assert len(audit["checkpoints"]) == 6
    assert all(row["match"] for row in audit["checkpoints"].values())
    assert all(row["match"] for row in audit["scope19_export_hashes"].values())


def test_scope20_legacy_preprocess_mismatch_is_reproduced_and_corrected():
    trace = read_json("parity_trace.json")
    reproduction = trace["scope19_failure_reproduction"]
    assert reproduction["mismatch_count"] == 48
    assert reproduction["total"] == 48
    assert trace["preprocess_policy"]["auto"] is False
    assert trace["test_accessed"] is False


def test_scope20_backend_contracts_and_single_nms_gate():
    trace = read_json("parity_trace.json")
    rows = trace["records"]
    assert rows
    assert all(row["final"]["status"] in {"PARITY_PASS", "PARITY_FAIL"} for row in rows)
    yolo26_ncnn = [row for row in rows if "yolo26n" in row["run_id"] and row["backend"] == "ncnn"]
    assert yolo26_ncnn
    assert all(row["first_divergence"] == "output_contract" for row in yolo26_ncnn)
    assert all(row["pytorch_raw_shape"] == [1, 300, 6] for row in yolo26_ncnn)
    assert all(row["backend_raw_shape"][1] == 5 for row in yolo26_ncnn)


def test_scope20_parity_fail_backend_cannot_be_ready():
    evidence = Path(ROOT / "docs/tracking/scope20/SCOPE20_MODEL_SELECTION_EVIDENCE.md").read_text(encoding="utf-8")
    assert "PARITY_FAIL" in evidence
    assert "DIAGNOSTIC_ONLY" in evidence
    assert "NO_MODEL_FROZEN" not in evidence or "pending" in evidence.lower()


def test_scope20_calibration_is_exactly_locked_train_only():
    calibration = read_json("int8_calibration.json")
    assert calibration["status"] == "PASS"
    assert calibration["test_accessed"] is False
    assert len(calibration["records"]) == 6
    assert all(row["source_split"] == "train" and row["sample_count"] == 128 for row in calibration["records"])
    assert all("test" not in sample.lower() for row in calibration["records"] for sample in row["sample_ids"])


def test_scope20_int8_blocked_outputs_are_not_ready():
    reports = sorted(RUNTIME.glob("int8_conversion_*_int8.json"))
    assert len(reports) == 6
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in reports]
    assert all(row["status"] == "BLOCKED" for row in rows)
    assert all(not row["artifacts"] for row in rows)


def test_scope20_pi_identity_gate_blocks_non_pi_host():
    pi = read_json("pi_input_audit.json")
    assert pi["status"] == "PI_BENCHMARK_BLOCKED"
    assert pi["identity"]["uname_m"] == "x86_64"
    assert pi["test_accessed"] is False
