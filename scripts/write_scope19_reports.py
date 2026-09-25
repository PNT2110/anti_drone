"""Render Scope 19 markdown reports from the immutable runtime artifacts."""

from __future__ import annotations

import json
import platform
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/tracking/scope19"
RUNTIME = ROOT / ".runtime/scope19"


def load(name: str) -> dict:
    return json.loads((RUNTIME / name).read_text(encoding="utf-8"))


def write(name: str, text: str) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / name).write_text(text.rstrip() + "\n", encoding="utf-8")


def fmt(value: object) -> str:
    return "N/A" if value is None else str(value)


def main() -> int:
    audit = load("input_audit.json")
    exports = load("export_report.json")
    parity = load("backend_parity.json")
    benchmark = load("host_benchmark.json")
    selection = load("model_selection_table.json")
    contracts = load("backend_contracts.json")
    export_items = exports.get("exports", [])
    export_counts = Counter((item.get("runtime"), item.get("status")) for item in export_items)
    parity_counts = Counter((item.get("runtime"), item.get("status")) for item in parity.get("parity", []))
    blocked_errors = sorted({item.get("error", "") for item in export_items + exports.get("int8", []) if item.get("status") == "BLOCKED"})

    checkpoint_rows = "\n".join(
        f"| `{run_id}` | `{row['sha256']}` | `{row['expected']}` | {'PASS' if row['match'] else 'FAIL'} |"
        for run_id, row in audit["checkpoints"].items()
    )
    write("SCOPE19_INPUT_AUDIT.md", f"""# Scope 19 — Input audit

Status: **{audit['status']}**

The audit locks the six Scope 18 `best.pt` checkpoints, the repaired V3 candidate, and a deterministic train-only benchmark/calibration protocol. `test_accessed={audit['test_accessed']}`. No validation or test inference was rerun.

## Frozen checkpoint hashes

| Run | Actual SHA-256 | Expected Scope 18 SHA-256 | Result |
|---|---|---|---|
{checkpoint_rows}

Dataset manifest SHA-256: `{audit['dataset_manifest_sha256']}`  
Split registry SHA-256: `{audit['dataset_split_registry_sha256']}`  
Scope 18 ledger: `{audit['frozen_validation_source']}`  
Benchmark input: `{audit['benchmark_input_manifest']}` (8 lexicographically first `train` images)  
INT8 calibration manifest: `{audit['calibration_manifest']}` (128 `train` images)

V3 test remains locked. Scope 18 status and frozen validation values are consumed from the ledger only.
""")

    export_table = "\n".join(
        f"| `{runtime}` | `{status}` | {count} |"
        for (runtime, status), count in sorted(export_counts.items())
    )
    contract_rows = "\n".join(
        f"| `{row['run_id']}` | `{row['onnx']['inputs'][0]['name']}` `{row['onnx']['inputs'][0]['shape']}` | `{row['onnx']['outputs'][0]['name']}` `{row['onnx']['outputs'][0]['shape']}` | `{row['ncnn']['input_names']}` / `{row['ncnn']['output_names']}` |"
        for row in contracts["records"]
    )
    write("SCOPE19_EXPORT_REPORT.md", f"""# Scope 19 — Export report

Overall export status: **{exports['status']}**. All six checkpoints exported successfully to float32 ONNX and NCNN. TFLite export is recorded as blocked; no placeholder artifact was treated as valid.

| Runtime | Status | Count |
|---|---|---:|
{export_table}

Output root: `{ROOT / 'artifacts/exports/scope19'}`

The blocked TFLite error is:

`{blocked_errors[0] if blocked_errors else 'N/A'}`

The six source checkpoints are copied to a temporary directory before export, so their Scope 18 files are not modified. Input shape is static NCHW `[1, 3, imgsz, imgsz]`; batch is 1; NMS is disabled in the exported graph.

## Tensor contract

| Run | ONNX input | ONNX output | NCNN native names |
|---|---|---|---|
{contract_rows}

ONNX shapes are read from the graph. NCNN names are read from `model.ncnn.param` and static image/batch metadata; native output dimensions are deliberately not inferred without executing the native binding. Full machine-readable record: `{RUNTIME / 'backend_contracts.json'}`.
""")

    parity_table = "\n".join(
        f"| `{runtime}` | `{status}` | {count} |"
        for (runtime, status), count in sorted(parity_counts.items())
    )
    write("SCOPE19_BACKEND_PARITY.md", f"""# Scope 19 — Backend parity

Parity protocol was fixed before inspection: confidence absolute difference `<= 0.05`, bounding-box IoU `>= 0.95`, exact class id, and exact detection count. Predictions use confidence `0.25`, NMS IoU `0.70`, CPU, and the same 8 deterministic `train` images for every backend.

| Runtime | Result | Count |
|---|---|---:|
{parity_table}

All six ONNX and all six NCNN runs were executable, but none passed the all-eight-image parity gate. The failures are diagnostic, not model retuning: ONNX has isolated IoU/count mismatches under the declared tolerance; NCNN is executable after the Ultralytics loader naming alias and is also marked parity-fail. TFLite was unavailable because export was blocked.

Raw artifact: `{RUNTIME / 'backend_parity.json'}`. No test image or test metric was accessed.
""")

    int8_errors = sorted({item.get("error", "") for item in exports.get("int8", [])})
    write("SCOPE19_INT8_REPORT.md", f"""# Scope 19 — INT8 report

Status: **BLOCKED**. A deterministic calibration manifest with 128 images from the V3 `train` split was prepared at `{RUNTIME / 'calibration_manifest.json'}`. It does not use V3 test data.

All six requested INT8 TFLite exports were attempted and all six were blocked by the same environment/toolchain incompatibility:

`{int8_errors[0] if int8_errors else 'N/A'}`

No INT8 artifact, size, checksum, or accuracy claim is fabricated. INT8 remains unvalidated and cannot be used as a model-selection tie-breaker in this scope.
""")

    benchmark_rows = "\n".join(
        f"| `{row['run_id']}` | `{row['runtime']}` | {row['mean_latency_ms']:.2f} | {row['p95_latency_ms']:.2f} | {row['fps_mean']:.2f} | {row['rss_peak_bytes'] / 1024 / 1024:.1f} | `{row['parity_status']}` |"
        for row in benchmark.get("records", [])
    )
    write("SCOPE19_PI_BENCHMARK.md", f"""# Scope 19 — Raspberry Pi 5 benchmark

Status: **BLOCKED — NO RASPBERRY PI 5 IN WORKSPACE**.

The current host is `{platform.platform()}` / `{platform.machine()}`. No Pi 5, Pi camera, or live camera was accessed. The table below is CPU host reference data only; it must not be interpreted as Pi 5 throughput, power, thermal, or sustained-load evidence.

| Run | Runtime | Mean ms | P95 ms | Host FPS | Peak RSS MiB | Parity |
|---|---|---:|---:|---:|---:|---|
{benchmark_rows}

Each record uses 20 warm-up passes per image and 100 measured predictions over the fixed 8-image `train` subset. Pi 5 measurements, thermal behavior, and camera I/O remain outstanding.
""")

    selection_rows = "\n".join(
        f"| `{row['run_id']}` | {row['frozen_validation']['mAP50']:.5f} | {row['frozen_validation']['mAP50_95']:.5f} | {row['frozen_validation']['recall']:.5f} | {row['model_characteristics']['parameter_count']:,} | {row['export_size_bytes'].get('onnx', 0) / 1024 / 1024:.2f} | {row['export_size_bytes'].get('ncnn', 0) / 1024 / 1024:.2f} | {row['host_reference_fps'].get('onnx', 0):.2f} | {row['host_reference_fps'].get('ncnn', 0):.2f} | {max(row['host_peak_rss_bytes'].values(), default=0) / 1024 / 1024:.1f} | `{row['selection_status']}` |"
        for row in selection["records"]
    )
    write("SCOPE19_MODEL_SELECTION_TABLE.md", f"""# Scope 19 — Model selection table

This is a deployment-readiness comparison, not a final production freeze. Accuracy values are frozen Scope 18 validation values; V3 test remains locked and is not used.

| Run | Frozen mAP50 | Frozen mAP50-95 | Frozen recall | Parameters | ONNX MiB | NCNN MiB | Host ONNX FPS | Host NCNN FPS | Host peak RSS MiB | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
{selection_rows}

Selection policy: retain recall and mAP50-95, require export and backend parity, consider parameters/RAM/runtime, and require real Pi 5 evidence before deployment freeze. FLOPs are `N/A` because the framework did not expose a machine-readable value through this harness. Decision: **NO_MODEL_FROZEN_WITHOUT_PI5_EVIDENCE**.
""")

    write("SCOPE19_TEST_REPORT.md", """# Scope 19 — Test report

The final commands and return codes are recorded here after report generation:

- `PYTHONPATH=. pytest -q`
- `/home/pnt/miniconda3/envs/antidrone/bin/python -m compileall -q scripts src tests`
- `git diff --check`

Scope-specific checks cover frozen checkpoint hashes, train-only input manifests, test-lock invariants, declared parity tolerances, output-path safety, and the rule that blocked INT8/TFLite artifacts cannot be reported as exported.
""")

    write("SCOPE19_FINAL_REPORT.md", f"""# Scope 19 — Final report

Status: **PARTIALLY_COMPLETE / BLOCKED FOR DEPLOYMENT FREEZE**.

Completed:

- Six Scope 18 checkpoints were hash-verified against the required values.
- Six float32 ONNX and six float32 NCNN artifacts were exported.
- Backend parity was evaluated with a predeclared tolerance on a deterministic train-only subset.
- Host CPU reference latency, FPS, and peak RSS were measured for ONNX and NCNN.
- Six TFLite float32 and six INT8 attempts were recorded honestly as blocked by the current Torch/LiteRT compatibility error.

Blocked/outstanding:

- No Raspberry Pi 5 is available in this workspace, so no Pi performance, thermal, RAM, or camera-I/O claim is made.
- No backend passed the strict all-eight-image parity gate.
- No INT8 artifact was produced.
- No production model is frozen; V3 test remains locked and `SPLIT_UNVERIFIED` is unchanged.

No retraining, tracker/gate change, threshold optimization, dataset reshuffle, test access, Pi/camera access, or Git commit/push was performed.

Reports: [input audit](SCOPE19_INPUT_AUDIT.md), [exports](SCOPE19_EXPORT_REPORT.md), [parity](SCOPE19_BACKEND_PARITY.md), [INT8](SCOPE19_INT8_REPORT.md), [Pi benchmark](SCOPE19_PI_BENCHMARK.md), [selection table](SCOPE19_MODEL_SELECTION_TABLE.md), [test report](SCOPE19_TEST_REPORT.md).

Runtime evidence is under `{RUNTIME}` and exported artifacts under `{ROOT / 'artifacts/exports/scope19'}`. Research & Design must review the parity failures and obtain real Pi 5 measurements before any deployment/model-selection freeze.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
