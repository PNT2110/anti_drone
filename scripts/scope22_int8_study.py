#!/usr/bin/env python3
"""Scope 22 NCNN INT8 study for the frozen three-candidate shortlist."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope22"
EXPORTS = ROOT / "artifacts/exports/scope22"
SCOPE19 = ROOT / ".runtime/scope19"
SCOPE20 = ROOT / ".runtime/scope20"
SCOPE21 = ROOT / ".runtime/scope21"
NCNN_TOOLS = ROOT / ".runtime/scope22/toolchain/ncnn-build/tools/quantize"
NCNN_OPT = ROOT / ".runtime/scope22/toolchain/ncnn-build/tools/ncnnoptimize"
APPROVED = [
    ("scope18-yolov8n-480", 480),
    ("scope18-yolov8n-640", 640),
    ("scope18-yolov11n-480", 480),
]
EXPECTED_EXPORTS = {
    "scope18-yolov8n-480": "b5976222cb4493618dda9fe321ef1c5e2adb4734dddcd09099a3f8a615114874",
    "scope18-yolov8n-640": "03038bd5d495b16308c3fa44980330ff1d5e6f234ae93880a2ec40dcf1e159a2",
    "scope18-yolov11n-480": "c823fcf16a482f7975ef4a5e0662bb2ee8e996d8522f4ed1aa33c0d9bdd5c768",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def run(command: list[str], log_path: Path) -> dict:
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    log_path.write_text("$ " + " ".join(command) + "\n\nSTDOUT\n" + proc.stdout + "\nSTDERR\n" + proc.stderr)
    return {"command": command, "returncode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-8000:]}


def source_paths() -> dict[str, dict]:
    audit = json.loads((SCOPE20 / "input_audit.json").read_text())
    rows = {}
    for run_id, size in APPROVED:
        key = f"{run_id}:ncnn"
        item = audit["scope19_export_hashes"][key]
        root = Path(item["path"])
        rows[run_id] = {"run_id": run_id, "size": size, "root": str(root), "param": str(root / "model.ncnn.param"), "bin": str(root / "model.ncnn.bin"), "sha256": item["actual"], "expected_sha256": EXPECTED_EXPORTS[run_id], "match": item["actual"] == EXPECTED_EXPORTS[run_id]}
    return rows


def audit() -> dict:
    errors = []
    scope20 = json.loads((SCOPE20 / "input_audit.json").read_text())
    parity = json.loads((SCOPE20 / "parity_summary.json").read_text())
    scope21 = json.loads((SCOPE21 / "benchmark_results.json").read_text())
    calibration_path = SCOPE19 / "calibration_manifest.json"
    calibration = json.loads(calibration_path.read_text())
    if scope20.get("status") != "PASS" or scope20.get("test_accessed") is not False:
        errors.append("Scope 20 baseline audit is not PASS/test-locked")
    if calibration.get("count") != 128 or calibration.get("source_split") != "train" or calibration.get("test_accessed") is not False:
        errors.append("calibration manifest is not the exact 128-image train-only set")
    allowed = {(run_id, "ncnn") for run_id, _ in APPROVED}
    parity_status = {(x["run_id"], x["backend"]): x["status"] for x in parity["summary"]}
    for key in allowed:
        if parity_status.get(key) != "PARITY_PASS":
            errors.append(f"Scope 20 parity not PASS: {key}")
    for run_id, _ in APPROVED:
        row = next((x for x in scope21["results"] if x["candidate_id"] == f"{run_id}:ncnn"), None)
        if not row or row["status"] != "PI_BENCHMARK_PASS" or any(x["compare"]["status"] != "PARITY_PASS" for x in row["pi_parity"]):
            errors.append(f"Scope 21 Pi evidence not PASS: {run_id}:ncnn")
    sources = source_paths()
    for run_id, row in sources.items():
        if not row["match"] or not Path(row["param"]).is_file() or not Path(row["bin"]).is_file():
            errors.append(f"Scope 19 NCNN artifact changed/missing: {run_id}")
    image_list = RUNTIME / "calibration_images.txt"
    image_list.write_text("\n".join(calibration["paths"]) + "\n")
    toolchain = {
        "ncnn_python": importlib.metadata.version("ncnn"),
        "ncnn_source_tag": "20260526",
        "ncnn_source_commit": subprocess.run(["git", "-C", str(ROOT / ".runtime/scope22/toolchain/ncnn-src"), "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip(),
        "ncnnoptimize": str(NCNN_OPT),
        "ncnn2table": str(NCNN_TOOLS / "ncnn2table"),
        "ncnn2int8": str(NCNN_TOOLS / "ncnn2int8"),
        "python_api_quantize_only": True,
        "official_workflow": "ncnnoptimize (not needed for PNNX output) -> ncnn2table -> ncnn2int8",
    }
    result = {
        "status": "PASS" if not errors else "BLOCKED_INPUT_CHANGED",
        "errors": errors,
        "approved_candidates": [f"{run_id}:ncnn" for run_id, _ in APPROVED],
        "excluded": ["YOLO26 NCNN: Scope 20 PARITY_FAIL"],
        "scope20_dataset_manifest_sha256": scope20["dataset"]["manifest"],
        "scope20_split_registry_sha256": scope20["dataset"]["split_registry"],
        "calibration_manifest": {"path": str(calibration_path), "sha256": sha256(calibration_path), "count": calibration["count"], "source_split": calibration["source_split"], "test_accessed": calibration["test_accessed"], "image_list": str(image_list)},
        "sources": sources,
        "toolchain": toolchain,
        "test_accessed": False,
    }
    write_json(RUNTIME / "input_audit.json", result)
    write_json(RUNTIME / "toolchain_audit.json", toolchain)
    return result


def quantize(audit: dict) -> dict:
    if audit["status"] != "PASS":
        result = {"status": audit["status"], "candidates": [], "reason": audit["errors"]}
        write_json(RUNTIME / "int8_export.json", result)
        return result
    rows = []
    for run_id, size in APPROVED:
        src = Path(audit["sources"][run_id]["root"])
        out = EXPORTS / run_id / "int8/ncnn"
        work = RUNTIME / "work" / run_id
        out.mkdir(parents=True, exist_ok=True); work.mkdir(parents=True, exist_ok=True)
        table = work / "calibration.table"
        out_param = out / "model.ncnn.param"
        out_bin = out / "model.ncnn.bin"
        table_cmd = [str(NCNN_TOOLS / "ncnn2table"), str(src / "model.ncnn.param"), str(src / "model.ncnn.bin"), str(RUNTIME / "calibration_images.txt"), str(table), "mean=[0,0,0]", "norm=[0.003921568627,0.003921568627,0.003921568627]", f"shape=[{size},{size},3]", "pixel=RGB", "thread=4", "method=kl"]
        table_run = run(table_cmd, work / "ncnn2table.log")
        row = {"run_id": run_id, "size": size, "input_param": str(src / "model.ncnn.param"), "input_bin": str(src / "model.ncnn.bin"), "calibration_table": str(table), "calibration_table_sha256": sha256(table) if table.is_file() else None, "ncnn2table": table_run, "status": "INT8_BLOCKED"}
        if table_run["returncode"] == 0 and table.is_file():
            int8_cmd = [str(NCNN_TOOLS / "ncnn2int8"), str(src / "model.ncnn.param"), str(src / "model.ncnn.bin"), str(out_param), str(out_bin), str(table)]
            int8_run = run(int8_cmd, work / "ncnn2int8.log")
            row["ncnn2int8"] = int8_run
            if int8_run["returncode"] == 0 and out_param.is_file() and out_bin.is_file():
                text = out_param.read_text(errors="replace")
                markers = len(re.findall(r"\b8=[12]\b", text))
                row["artifact"] = {"param": str(out_param), "bin": str(out_bin), "param_sha256": sha256(out_param), "bin_sha256": sha256(out_bin), "param_bytes": out_param.stat().st_size, "bin_bytes": out_bin.stat().st_size, "int8_param_markers_8_eq_1_or_2": markers}
                row["quantization_evidence"] = {"weight_dtype": "int8 claimed only when ncnn2int8 succeeds and param markers are present", "activation_dtype": "NCNN int8 graph scales from calibration table", "scale_format": "NCNN calibration table"}
                row["status"] = "INT8_RUNTIME_CANDIDATE" if markers > 0 else "INT8_BLOCKED_NO_GRAPH_MARKERS"
        rows.append(row)
    result = {"status": "PASS" if any(row["status"] == "INT8_RUNTIME_CANDIDATE" for row in rows) else "INT8_PATH_BLOCKED", "candidates": rows, "calibration": audit["calibration_manifest"], "test_accessed": False}
    write_json(RUNTIME / "int8_export.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--phase", choices=("audit", "quantize", "all"), default="all")
    args = parser.parse_args(); RUNTIME.mkdir(parents=True, exist_ok=True); EXPORTS.mkdir(parents=True, exist_ok=True)
    baseline = audit()
    if args.phase == "audit": print(json.dumps(baseline, indent=2)); return 0 if baseline["status"] == "PASS" else 2
    export = quantize(baseline)
    print(json.dumps({"baseline": baseline["status"], "int8": export["status"]}, indent=2))
    return 0 if export["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
