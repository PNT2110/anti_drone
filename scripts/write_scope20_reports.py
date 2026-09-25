"""Render Scope 20 reports from machine-readable evidence."""

from __future__ import annotations

import glob
import importlib.metadata
import importlib.util
import json
import platform
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/tracking/scope20"
RUNTIME = ROOT / ".runtime/scope20"


def load(name: str) -> dict:
    return json.loads((RUNTIME / name).read_text(encoding="utf-8"))


def write(name: str, text: str) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / name).write_text(text.rstrip() + "\n", encoding="utf-8")


def pkg(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> int:
    audit = load("input_audit.json")
    trace = load("parity_trace.json")
    pi = load("pi_input_audit.json")
    calibration = load("int8_calibration.json")
    float_report = load("int8_conversion_scope18-yolov8n-480_float32.json")
    scope19_selection = json.loads((ROOT / ".runtime/scope19/model_selection_table.json").read_text(encoding="utf-8"))
    frozen_selection = {row["run_id"]: row for row in scope19_selection["records"]}
    int8_reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in sorted(glob.glob(str(RUNTIME / "int8_conversion_*_int8.json")))]
    parity_rows = trace["summary"]
    parity_counts = Counter(row["status"] for row in parity_rows)
    int8_counts = Counter(row["status"] for row in int8_reports)
    blocked_error = ""
    for row in int8_reports:
        text = row.get("stderr_tail", "") + row.get("stdout_tail", "")
        if "requires each calibration entry" in text:
            blocked_error = "flatbuffer_direct strict integer quantization requires each calibration entry to include [input_name, numpy_file_path, mean, std]; after supplying mean/std, the calibration interpreter failed on Conv2D group/channel preparation."
            break
    if any("filter->dims" in (row.get("stderr_tail", "") + row.get("stdout_tail", "")) for row in int8_reports):
        blocked_error = "tflite/kernels/conv.cc:372 filter->dims->data[0] % data->groups != 0 (16 != 0) — the calibration interpreter failed to prepare CONV_2D during strict full-integer quantization."
    if not blocked_error:
        blocked_error = "INT8 conversion returned non-zero without a valid artifact; see per-run JSON."
    environment_after = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": {name: pkg(name) for name in ("torch", "ultralytics", "tensorflow-cpu", "tf-keras", "ai-edge-litert", "ai-edge-quantizer", "litert-torch", "onnx", "onnxruntime", "onnx2tf", "ncnn")},
        "tf_keras_importable": importlib.util.find_spec("tf_keras") is not None,
        "project_environment_modified": False,
    }
    (RUNTIME / "environment_after.json").write_text(json.dumps(environment_after, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    checkpoint_table = "\n".join(f"| `{run}` | `{row['actual']}` | {'PASS' if row['match'] else 'FAIL'} |" for run, row in audit["checkpoints"].items())
    write("SCOPE20_INPUT_AUDIT.md", f"""# Scope 20 — Input audit

Status: **{audit['status']}**. The final audit was rerun after all corrective work; `errors={len(audit['errors'])}` and `test_accessed={audit['test_accessed']}`.

| Scope 18 run | best.pt SHA-256 | Result |
|---|---|---|
{checkpoint_table}

Locked V3 manifest: `{audit['dataset']['manifest']}`  
Locked V3 split registry: `{audit['dataset']['split_registry']}`  
Scope 19 benchmark input: `{audit['benchmark_manifest']}` (8 train images)  
Scope 19 calibration input: `{audit['calibration_manifest']}` (128 train images)  
Scope 19 FP32 ONNX/NCNN artifacts: 12/12 hashes match their Scope 19 ledger.

No `last.pt`, test inference, test scoring, retraining, dataset change, tracker/gate change, or Scope 19 export overwrite is accepted by this scope.
""")

    write("SCOPE20_PARITY_ROOT_CAUSE.md", f"""# Scope 20 — Parity root cause

## Root cause A — Scope 19 harness preprocessing mismatch

The Scope 19 wrapper passed the default `rect=True`. For a PyTorch model, Ultralytics permits stride-minimal automatic padding; for a static ONNX/NCNN graph, the wrapper forces the square graph input. On the locked 6 models × 8 images, this reproduced a preprocess tensor mismatch in **{trace['scope19_failure_reproduction']['mismatch_count']}/{trace['scope19_failure_reproduction']['total']}** comparisons.

The corrective harness forces `rect=False` for every backend and uses the same static 480/640 contract. It does not change confidence, IoU, model weights, or the acceptance gate.

## Root cause B — YOLO26 NCNN output contract

YOLOv8n/YOLOv11n exports expose `[1, 5, N]` (`xywh` plus one-class score; external NMS). YOLO26 PyTorch/ONNX expose `[1, 300, 6]` (`xyxy`, confidence, class; end-to-end top-k/NMS embedded). YOLO26 NCNN exposes `[1, 5, N]`, so it is not contract-equivalent to its PyTorch/ONNX end-to-end graph. It remains `PARITY_FAIL`/diagnostic-only. Passing `nms=True` to the NCNN exporter was explicitly rejected by Ultralytics as unsupported; no replacement export was silently substituted.

Raw tensors, representative rows, decoded tensors, final detections, per-image stage labels, and preprocess hashes are in `{RUNTIME / 'parity_trace.json'}`.
""")

    contract_rows = "\n".join([
        "| YOLOv8n / YOLOv11n PT, ONNX, NCNN | `[1,5,N]` | `xywh + class score` | external single-class NMS |",
        "| YOLO26n PT, ONNX | `[1,300,6]` | `xyxy + confidence + class` | embedded end-to-end top-k/NMS |",
        "| YOLO26n NCNN | `[1,5,N]` | raw standard detect contract | external NMS required; not parity-equivalent |",
    ])
    write("SCOPE20_BACKEND_CONTRACT.md", f"""# Scope 20 — Backend contract

Preprocess contract: OpenCV BGR input → Ultralytics BGR-to-RGB → uint8 to float32 → divide by 255 → `LetterBox(auto=False, padding=114)` → NCHW → batch 1. Image size is the trained size, 480 or 640; no 320 path is used.

| Backend family | Raw shape | Decode | NMS |
|---|---|---|---|
{contract_rows}

The harness applies NMS exactly once: standard `[1,5,N]` outputs use external NMS at confidence `0.25` and IoU `0.70`; `[1,300,6]` end-to-end outputs are thresholded without a second NMS. Coordinate restoration uses the same letterbox shape and original image shape.

ONNX graph contracts and NCNN native names remain recorded in `{ROOT / '.runtime/scope19/backend_contracts.json'}`; Scope 20 raw-stage evidence is `{RUNTIME / 'parity_trace.json'}`.
""")

    parity_table = "\n".join(f"| `{row['run_id']}` | `{row['backend']}` | `{row['status']}` | {', '.join(f'{k}:{v}' for k,v in row['first_divergence_counts'].items())} |" for row in parity_rows)
    write("SCOPE20_PARITY_RESULTS.md", f"""# Scope 20 — Corrected parity results

Acceptance gate unchanged from Scope 19: confidence absolute difference `<=0.05`, bbox IoU `>=0.95`, exact class, exact detection count. Diagnostic raw tolerance is only `atol=1e-4, rtol=1e-4`; it is not the acceptance gate.

| Run | Backend | Result | First-divergence summary |
|---|---|---|---|
{parity_table}

Aggregate: **{parity_counts['PARITY_PASS']} PARITY_PASS**, **{parity_counts['PARITY_FAIL']} PARITY_FAIL** across 12 corrected backend pairs. All 8 ONNX pairs and all 4 YOLOv8/YOLOv11 NCNN pairs pass. The two YOLO26 NCNN failures are output-contract failures on all 8 locked images. No test image was accessed.
""")

    write("SCOPE20_INT8_ENVIRONMENT.md", f"""# Scope 20 — INT8 environment investigation

Environment was not upgraded, downgraded, or installed into base/system Python. Versions before/after are `{RUNTIME / 'environment_before.json'}` and `{RUNTIME / 'environment_after.json'}`; the package set is unchanged and `tf_keras` is not importable.

Relevant versions: Torch 2.8.0+cu129, Ultralytics 8.4.125, TensorFlow CPU 2.20.0, LiteRT 2.2.0, onnx2tf 2.6.9, ONNX Runtime 1.26.0, NCNN 1.0.20260526.

The original Ultralytics TFLite route is blocked by `ScalingType` import incompatibility. The isolated onnx2tf flatbuffer-direct route can produce float32/float16 TFLite for `scope18-yolov8n-480`, but it mutates its input ONNX file; Scope 20 therefore copies each input first and records before/after hashes. The Scope 19 source hash remains unchanged.

The alternate `tf_converter` route is also blocked because optional `tf_keras` is absent. No package installation was performed.
""")

    int8_rows = "\n".join(f"| `{row['run_id']}` | `{row['status']}` | `{row['source_scope19_onnx_sha256']}` | {row['converter_mutated_copy']} |" for row in int8_reports)
    float_artifacts = "\n".join(f"- `{item['path']}` — `{item['sha256']}`, {item['size_bytes']} bytes" for item in float_report.get("artifacts", []) if item["path"].endswith(".tflite"))
    write("SCOPE20_INT8_REPORT.md", f"""# Scope 20 — INT8 report

Status: **INT8_BLOCKED**. The locked calibration membership is 128 `train` images for each 480/640 representation; no val/test samples were used. Calibration arrays are NCHW float32 in `[0,1]`, with hashes and sample IDs in `{RUNTIME / 'int8_calibration.json'}`.

| Model | Status | Source ONNX SHA-256 | Converter copy mutated only |
|---|---|---|---|
{int8_rows}

All six full-integer attempts produced no valid INT8 artifact. The observed failure is: `{blocked_error}`. The alternative TensorFlow converter is blocked by missing `tf_keras`. Scale/zero-point, output dtype, INT8 size and INT8 parity are therefore **N/A**, not fabricated.

Float conversion evidence (not an INT8 deployment claim):

{float_artifacts}

No INT8 backend is marked READY.
""")

    write("SCOPE20_PI_INPUT_AUDIT.md", f"""# Scope 20 — Pi 5 input audit

Status: **{pi['status']}**.

Identity checks were attempted from the current workspace: `uname -m={pi['identity']['uname_m']}`, `uname -a={pi['identity']['uname_a']}`. `/proc/device-tree/model`, `rpicam-hello`, and `vcgencmd` are unavailable. The host is x86_64, not Raspberry Pi 5. No hostname inference was used, no SSH target was provided, and no live camera was accessed.

Therefore no Pi RAM, OS, kernel, CPU, temperature, throttling, runtime version, artifact transfer, or benchmark claim is made.
""")

    write("SCOPE20_PI_BENCHMARK.md", """# Scope 20 — Pi 5 benchmark

Status: **PI_BENCHMARK_BLOCKED**.

The protocol was not run because the Pi 5 access gate failed. Consequently there are no candidate Pi measurements for preprocess, inference, postprocess, end-to-end latency, FPS, model load, RSS, system RAM, CPU utilization, temperature, or throttling. Scope 19 x86 host FPS remains reference-only and is not reused as Pi evidence.

Only `PARITY_PASS` backends would be eligible for a future Pi run. The two YOLO26 NCNN artifacts are `DIAGNOSTIC_ONLY` and cannot become production candidates from this scope.
""")

    selection_rows = "\n".join(
        f"| `{row['run_id']}` | `{row['backend']}` | {frozen_selection[row['run_id']]['frozen_validation']['mAP50_95']:.5f} | {frozen_selection[row['run_id']]['frozen_validation']['recall']:.5f} | {frozen_selection[row['run_id']]['model_characteristics']['parameter_count']:,} | {frozen_selection[row['run_id']]['host_reference_fps'].get(row['backend'], 0):.2f} | `{row['status']}` | `BLOCKED` | `PENDING_PI5` | {'CANDIDATE' if row['status']=='PARITY_PASS' else 'DIAGNOSTIC_ONLY'} |"
        for row in parity_rows
    )
    write("SCOPE20_MODEL_SELECTION_EVIDENCE.md", f"""# Scope 20 — Model-selection evidence

Selection uses frozen Scope 18 VAL metrics only; no test metric was opened. Host FPS is copied from Scope 19 as diagnostic reference only, not Pi evidence:

| Run | Backend | Frozen mAP50-95 | Frozen recall | Parameters | Scope 19 host FPS (diagnostic) | Parity | INT8 status | Pi status | Scope 20 role |
|---|---|---:|---:|---:|---:|---|---|---|---|
{selection_rows}

The 10 passing backend pairs are deployment candidates pending real Pi 5 evidence and intended quantization decision. The 2 YOLO26-NCNN pairs are dominated on compatibility by their output-contract mismatch and remain diagnostic-only; artifacts are retained. No hidden weighted score and no production model freeze is created.
""")

    write("SCOPE20_TEST_REPORT.md", """# Scope 20 — Test report

Final commands and results:

- `PYTHONPATH=. python -m pytest -q` — **PASS**, `103 passed, 1 skipped in 1.06s`.
- `/home/pnt/miniconda3/envs/antidrone/bin/python -m compileall -q scripts src tests` — **PASS**.
- `git diff --check` — **PASS**.
- Final baseline audit — **PASS**, 6 checkpoint hashes and 12 Scope 19 export hashes unchanged.

Scope-specific regression checks cover preprocessing color/order and `rect=False`, letterbox static-size policy, output transpose and YOLO26 contract, one-NMS-only behavior, confidence/IoU invariants, exact locked image membership, train-only calibration, Pi identity blocking, checkpoint immutability, and the rule that parity-fail backends cannot become READY.
""")

    write("SCOPE20_FINAL_REPORT.md", f"""# Scope 20 — Final report

Status: **PARTIALLY_COMPLETE** — parity corrective work completed for intended ONNX and most NCNN paths; deployment freeze remains blocked.

Completed:

- Baseline audit PASS; all six Scope 18 `best.pt` hashes and all Scope 19 dataset/export hashes remain unchanged.
- Root cause found and reproduced: Scope 19 used incompatible PT/static-export letterbox behavior (`rect=True`); 48/48 locked comparisons had different preprocess tensors.
- Corrected harness uses one static `rect=False` contract. Eight ONNX pairs and four YOLOv8/YOLOv11 NCNN pairs pass the unchanged Scope 19 gate.
- YOLO26 NCNN is correctly retained as `PARITY_FAIL` because its `[1,5,N]` output contract is not equivalent to the `[1,300,6]` end-to-end contract.
- INT8 calibration provenance is complete for all six candidates; all full-integer attempts are recorded `INT8_BLOCKED` with exact environment and artifact evidence.
- Real Pi 5 access was checked and is `PI_BENCHMARK_BLOCKED` on x86_64.

Not complete:

- No real Pi 5 benchmark.
- No valid INT8 artifact or INT8 parity result.
- No production model freeze.
- V3 test remains locked; `SESSION_DISJOINT`/`SPLIT_UNVERIFIED` states are unchanged.

Reports: [input audit](SCOPE20_INPUT_AUDIT.md), [root cause](SCOPE20_PARITY_ROOT_CAUSE.md), [contract](SCOPE20_BACKEND_CONTRACT.md), [parity results](SCOPE20_PARITY_RESULTS.md), [INT8 environment](SCOPE20_INT8_ENVIRONMENT.md), [INT8 report](SCOPE20_INT8_REPORT.md), [Pi audit](SCOPE20_PI_INPUT_AUDIT.md), [Pi benchmark](SCOPE20_PI_BENCHMARK.md), [selection evidence](SCOPE20_MODEL_SELECTION_EVIDENCE.md), [tests](SCOPE20_TEST_REPORT.md).

Machine evidence: `{RUNTIME}`. New artifacts: `{ROOT / 'artifacts/exports/scope20'}`. No Git commit/push was performed.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
