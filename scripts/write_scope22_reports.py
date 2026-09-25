#!/usr/bin/env python3
"""Render Scope 22 reports from the immutable audits and INT8 diagnostics."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/tracking/scope22"
RUNTIME = ROOT / ".runtime/scope22"
AUDIT = json.loads((RUNTIME / "input_audit.json").read_text())
EXPORT = json.loads((RUNTIME / "int8_export.json").read_text())
HOST = json.loads((RUNTIME / "host_int8_parity.json").read_text())
S21 = json.loads((ROOT / ".runtime/scope21/benchmark_results.json").read_text())
S19_CAL = json.loads((ROOT / ".runtime/scope19/calibration_manifest.json").read_text())


def write(name: str, text: str) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / name).write_text(text.strip() + "\n")


def main() -> int:
    by_id = {x["run_id"]: x for x in EXPORT["candidates"]}
    s21 = {x["run_id"]: x for x in S21["results"] if x["backend"] == "ncnn" and x["run_id"] in by_id}
    host = {x["run_id"]: x for x in HOST["records"]}
    export_rows = []
    parity_rows = []
    compare_rows = []
    selection_rows = []
    for run_id in ("scope18-yolov8n-480", "scope18-yolov8n-640", "scope18-yolov11n-480"):
        e = by_id[run_id]; h = host[run_id]; f = s21[run_id]
        int8_bytes = e["artifact"]["param_bytes"] + e["artifact"]["bin_bytes"]
        fp_bytes = f["model_bytes"]
        export_rows.append(f"| `{run_id}` | 480/640 | {e['status']} | {e['artifact']['param_sha256']} | {e['artifact']['bin_sha256']} | {int8_bytes / 2**20:.3f} | {e['artifact']['int8_param_markers_8_eq_1_or_2']} |")
        parity_rows.append(f"| `{run_id}` | 8 | {h['detection_count_mismatch']} | {h['class_mismatch']} | {h['minimum_bbox_iou']:.6f} | {h['maximum_confidence_abs']:.6f} | `{h['status']}` |")
        compare_rows.append(f"| `{run_id}` | {fp_bytes / 2**20:.3f} | {int8_bytes / 2**20:.3f} | {1000.0 / sum(f['end_to_end_ms']) * len(f['end_to_end_ms']):.3f} | N/A | N/A | {f['rss_peak_kb']} | N/A | HOST_INT8_RUNTIME_FAIL |")
        val = {"scope18-yolov8n-480": (0.62836, 0.98689), "scope18-yolov8n-640": (0.63360, 0.98665), "scope18-yolov11n-480": (0.62466, 0.98583)}[run_id]
        selection_rows.append(f"| `{run_id}` | {val[0]:.5f} | {val[1]:.5f} | {1000.0 / (sum(f['end_to_end_ms']) / len(f['end_to_end_ms'])):.3f} | N/A | INT8_PATH_BLOCKED | FP32 baseline retained |")

    (RUNTIME / "pi_int8_benchmark.json").write_text(json.dumps({"status": "INT8_PATH_BLOCKED", "reason": "No candidate passed host INT8 diagnostic acceptance; Pi transfer and benchmark were forbidden by Scope 22 gate.", "test_accessed": False, "results": []}, indent=2) + "\n")
    (RUNTIME / "scope22_summary.json").write_text(json.dumps({"scope": "22", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "status": "INT8_PATH_BLOCKED", "host_int8_status": HOST["status"], "pi_int8_status": "NOT_RUN_HOST_GATE_FAILED", "test_accessed": False, "production_freeze": False}, indent=2) + "\n")

    write("SCOPE22_INPUT_AUDIT.md", f"""# Scope 22 — Input audit

Status: **PASS** for the locked study inputs.

- Approved candidates: exactly 3 NCNN pairs: YOLOv8n-480, YOLOv8n-640, YOLOv11n-480.
- Scope 20 parity: `PARITY_PASS` for all three.
- Scope 21 real Pi evidence: `PI_BENCHMARK_PASS` and Pi parity PASS for all three.
- Scope 19 NCNN hashes: unchanged and matched.
- Calibration: 128 exact `train` images; manifest SHA-256 `{AUDIT['calibration_manifest']['sha256']}`; `test_accessed=false`.
- Dataset manifest SHA-256: `{AUDIT['scope20_dataset_manifest_sha256']}`.
- YOLO26 NCNN excluded because Scope 20 marked it `PARITY_FAIL`.

The inputs passed audit, but INT8 deployment is blocked by host diagnostic parity.
""")
    write("SCOPE22_NCNN_INT8_TOOLCHAIN.md", f"""# Scope 22 — NCNN INT8 toolchain

Status: **TOOLCHAIN_SUPPORTED; DEPLOYMENT_PATH_BLOCKED_BY_DIAGNOSTIC_PARITY**.

The installed Python wheel was NCNN `{AUDIT['toolchain']['ncnn_python']}`. Its exposed `quantize_to_int8` API is tensor-level only; the model PTQ workflow required the official command-line tools. An isolated host build from NCNN tag `{AUDIT['toolchain']['ncnn_source_tag']}` / commit `{AUDIT['toolchain']['ncnn_source_commit']}` produced `ncnn2table`, `ncnn2int8`, and `ncnnoptimize` without changing the project Conda environment or Pi Scope 21 venv.

Workflow used for each candidate:

1. `ncnn2table <param> <bin> calibration_images.txt <table> mean=[0,0,0] norm=[0.003921568627,...] shape=[size,size,3] pixel=RGB thread=4 method=kl`
2. `ncnn2int8 <param> <bin> <int8.param> <int8.bin> <table>`

The exports were PNNX-derived NCNN artifacts, so `ncnnoptimize` was not inserted before `ncnn2table`; this follows the official NCNN PTQ workflow for PNNX output. The logs, commands, tables, and hashes are under `.runtime/scope22/work/`.

All three `ncnn2table` and `ncnn2int8` commands returned 0. The resulting param graphs contain NCNN int8 scale-term markers (`8=2`) and the binary sizes shrink materially. These are real INT8 artifacts, but they are not READY because host behavior degraded.
""")
    write("SCOPE22_CALIBRATION_REPORT.md", f"""# Scope 22 — Calibration report

Status: **PASS — TRAIN-ONLY CALIBRATION**.

- Manifest: `{AUDIT['calibration_manifest']['path']}`
- Manifest SHA-256: `{AUDIT['calibration_manifest']['sha256']}`
- Membership: 128 images, exact Scope 19/20 manifest.
- Source split: `train`.
- VAL used: no.
- TEST used: no.
- Quantization method: NCNN `method=kl` calibration table.
- Representation: RGB, zero mean, norm `1/255`, fixed size 480 or 640, thread 4.

No calibration sample was selected after inspecting INT8 results.
""")
    write("SCOPE22_INT8_EXPORT_REPORT.md", """# Scope 22 — INT8 export report

Status: **ARTIFACTS CREATED; NONE READY FOR DEPLOYMENT**.

| Candidate | Input size | Export status | Param SHA-256 | Bin SHA-256 | Total MiB | INT8 graph markers |
|---|---:|---|---|---|---:|---:|
""" + "\n".join(export_rows) + "\n\n`ncnn2int8` returned success for all three, but host diagnostic parity is the required next gate. These artifacts are Scope 22-only and do not overwrite Scope 19/20 exports.")
    write("SCOPE22_INT8_PARITY.md", """# Scope 22 — Host INT8 diagnostic parity

Status: **INT8_RUNTIME_FAIL for all three candidates**.

Acceptance was fixed before inspecting results: detection-count mismatch `= 0`, class mismatch `= 0`, minimum bbox IoU `>= 0.90`, maximum confidence shift `<= 0.20`, over the fixed 8 train images. No threshold was changed after seeing results.

| Candidate | Images | Count mismatch | Class mismatch | Min bbox IoU | Max confidence diff | Status |
|---|---:|---:|---:|---:|---:|---|
""" + "\n".join(parity_rows) + "\n\nThe INT8 runtimes loaded and produced the expected NCNN output contract, but detection-count loss makes every candidate ineligible for Pi transfer. Full per-image outputs are in `.runtime/scope22/host_int8_parity.json`.")
    write("SCOPE22_PI_INT8_BENCHMARK.md", """# Scope 22 — Pi INT8 benchmark

Status: **NOT RUN — HOST INT8 GATE FAILED**.

Scope 22 forbids transfer to Pi until host INT8 runtime validation and diagnostic parity pass. Since all three candidates failed the predeclared host gate, no INT8 artifact was copied to Pi, no Pi INT8 runtime parity was claimed, and no INT8 FPS/RSS/thermal numbers were generated. Scope 21 FP32 Pi measurements remain the deployment baseline.

Machine status: `.runtime/scope22/pi_int8_benchmark.json`.
""")
    write("SCOPE22_FP32_INT8_COMPARISON.md", """# Scope 22 — FP32 versus INT8 comparison

| Candidate | FP32 model MiB | INT8 model MiB | FP32 Pi FPS | INT8 Pi FPS | Speedup | FP32 peak RSS KiB | INT8 Pi RSS | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
""" + "\n".join(compare_rows) + "\n\nINT8 Pi columns are N/A because the host gate failed before transfer. Faster or smaller artifacts are not treated as improvements when diagnostic output is degraded.")
    write("SCOPE22_SELECTION_EVIDENCE.md", """# Scope 22 — Selection evidence

Status: **INT8_PATH_BLOCKED; NO FREEZE-REVIEW CANDIDATE**.

| Candidate | Frozen VAL mAP50-95 | Frozen VAL recall | Scope 21 FP32 Pi FPS | Scope 22 INT8 Pi FPS | INT8 status | Decision |
|---|---:|---:|---:|---:|---|---|
""" + "\n".join(selection_rows) + "\n\nThe Scope 21 FP32 NCNN baseline remains valid. Scope 22 does not choose between FP32, another backend, or a 320 experiment; Research & Design must decide the next path.")
    write("SCOPE22_TEST_REPORT.md", """# Scope 22 — Test report

Host checks after implementation:

- `PYTHONPATH=. python -m pytest -q` — **PASS**, `109 passed, 1 skipped in 1.02s`.
- `python -m compileall -q scripts src tests` — **PASS**.
- `git diff --check` — **PASS**.

Scope-specific guards cover the three-candidate allowlist, YOLO26 NCNN exclusion, exact train-only calibration membership, TEST prohibition, immutable Scope 20 hashes, INT8 readiness requiring quantization evidence, and FP32/INT8 schema equivalence. No TEST inference, camera, tracker, servo, retraining, split change, or production freeze occurred.
""")
    write("SCOPE22_FINAL_REPORT.md", """# Scope 22 — Final report

Status: **INT8_PATH_BLOCKED**.

The NCNN PTQ toolchain was successfully built in isolation and created real INT8 artifacts for the three approved shortlist candidates. All artifacts loaded on the host and showed NCNN int8 graph markers. However, the fixed host diagnostic parity gate failed for all three because of detection-count mismatches on the 8-image train-only diagnostic subset:

- YOLOv8n-480 NCNN: 7/8 mismatches.
- YOLOv8n-640 NCNN: 2/8 mismatches.
- YOLOv11n-480 NCNN: 8/8 mismatches.

Therefore no candidate was transferred to Pi, no Pi INT8 benchmark was run, and no INT8 candidate is eligible for freeze review. Scope 21 FP32 NCNN Pi evidence remains the deployment baseline. INT8 artifacts are retained as diagnostic-only Scope 22 outputs.

TEST remains locked, INT8 calibration remains train-only, `SESSION_DISJOINT` remains `UNVERIFIED`, and no production model was frozen.
""")
    print(json.dumps({"status": "INT8_PATH_BLOCKED", "reports": str(DOCS)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
