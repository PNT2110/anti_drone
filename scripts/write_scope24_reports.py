#!/usr/bin/env python3
"""Write the bounded Scope 24 audit reports."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope24"
DOCS = ROOT / "docs" / "tracking" / "scope24"


def load(name: str):
    return json.loads((RUNTIME / name).read_text())


def write(name: str, body: str):
    (DOCS / name).write_text(body.rstrip() + "\n")


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    plan = load("tflite_plan.json")
    audit = load("tflite_artifact_audit.json")
    tflite = load("tflite_host_parity.json")
    ort = load("ort_host_parity.json")
    pi = load("pi_input_audit.json")
    summary = {
        "status": "PTQ_INT8_PATHS_EXHAUSTED_FOR_CURRENT_SCOPE",
        "ncnn_scope23": "NCNN_INT8_PTQ_BLOCKED",
        "tflite": "TFLITE_INT8_BLOCKED",
        "onnxruntime": "ORT_INT8_BLOCKED",
        "test_accessed": False,
        "pi_access": pi["status"],
        "pi_transfer": False,
        "production_freeze": False,
    }
    (RUNTIME / "final_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    write("SCOPE24_INPUT_AUDIT.md", """# Scope 24 — Input audit

Status: **frozen inputs PASS; alternate INT8 paths blocked**.

- Only `scope18-yolov8n-480` and `scope18-yolov8n-640` were evaluated.
- Scope 18 `best.pt`, Scope 20 FP32 parity, Scope 21 Pi FP32 evidence, Scope 22 artifacts, and Scope 23 conclusion were immutable baselines. No `last.pt` or TEST inference was used.
- Repaired V3 manifest SHA-256: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`.
- Repaired split registry SHA-256: `c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1`.
- Calibration: exact 128-image TRAIN membership, SHA-256 `4c582deab8ec13a23a0ecf0b1b806e6f3dd0c2c43f5a7dca06c785227e444b59`.
- Diagnostics: fixed 8 TRAIN images and frozen secondary 32 TRAIN images; `test_accessed=false`.
- Gates fixed before results: confidence `0.25`, NMS IoU `0.70`, count mismatch `0`, class mismatch `0`, min IoU `0.90`, max confidence shift `0.20`.

Frozen plans: [`tflite_plan.json`](../../../.runtime/scope24/tflite_plan.json) and [`ort_plan.json`](../../../.runtime/scope24/ort_plan.json).
""")

    write("SCOPE24_TFLITE_ENVIRONMENT.md", """# Scope 24 — TFLite environment

Project environment `/home/pnt/miniconda3/envs/antidrone` was not modified.

- T1 isolated environment: `/home/pnt/.venvs/antidrone_scope24_tflite`, Python 3.12.14, `onnx2tf 2.6.9`, `ai-edge-litert 2.1.2`, `onnx 1.20.1`, `onnxruntime 1.26.0`.
- T2 isolated environment: `/tmp/antidrone_scope24_t2_tflite`, TensorFlow 2.21.0, `tf-keras 2.21.0`, `onnx2tf 2.6.9`.
- Exact snapshots: `.runtime/scope24/tflite_env_before.txt` and `.runtime/scope24/tflite_env_after.txt`.
- Initial project-volume exhaustion was handled by placing only temporary environments/calibration arrays on `/home`/`/tmp`; no project data or baseline artifact was removed.
""")

    write("SCOPE24_TFLITE_EXPORT.md", """# Scope 24 — TFLite export

The predeclared paths were:

- T1: `onnx2tf --tflite_backend flatbuffer_direct --output_integer_quantized_tflite --input_quant_dtype int8 --output_quant_dtype int8`.
- T2: `onnx2tf --tflite_backend tf_converter` with the same full-integer settings, only after T1 runtime blocking.

T1 produced full-integer artifacts for both sizes, but a probe invocation failed at builtin `LOGISTIC` because the output scale was not `1/256`.

T2 produced a full-integer v8n-480 artifact. Its converter process did not terminate cleanly after writing it, so the artifact is diagnostic-only. T2 v8n-640 timed out at the bounded 180-second limit before writing a full-integer artifact.

No third converter path, version brute-force, NCNN E4+ experiment, or production overwrite was performed.
""")

    audit_rows = [f"| {x['run_id']} | {x['variant']} | {x['status']} | {x.get('invoke_status', 'N/A')} | {x.get('sha256', 'N/A')} |" for x in audit["rows"]]
    write("SCOPE24_TFLITE_QUANTIZATION_AUDIT.md", """# Scope 24 — TFLite quantization audit

| Model | Path | Classification | Probe invoke | SHA-256 |
|---|---|---|---|---|
""" + "\n".join(audit_rows) + """

T1/T2 valid artifacts use `int8` input/output tensors and quantized Conv operators. T1 input scale was `0.0039215689`, zero-point `-128`; output scales were `1.9316361` (480) and `2.5554228` (640), producing the T1 `LOGISTIC` runtime block.

T2 v8n-480 loaded and invoked as full integer, but its output scale `1.9316361` quantized the confidence row to zero on the diagnostic inputs. This is a real contract/parity failure, not a relaxed gate.
""")

    rec = next(x for x in tflite["records"] if x["run_id"] == "scope18-yolov8n-480")
    f, s = rec["fixed_8"], rec["secondary_32"]
    write("SCOPE24_TFLITE_HOST_PARITY.md", f"""# Scope 24 — TFLite host parity

T2 v8n-480 host parity: **FAIL**.

- Fixed 8: count mismatch `{f['count_mismatch']}/8`, class mismatch `{f['class_mismatch']}`, min IoU `{f['minimum_bbox_iou']:.6f}`, max confidence shift `{f['maximum_confidence_abs']:.6f}`.
- Secondary 32: count mismatch `{s['count_mismatch']}/32`, class mismatch `{s['class_mismatch']}`, min IoU `{s['minimum_bbox_iou']:.6f}`, max confidence shift `{s['maximum_confidence_abs']:.6f}`.
- T1 v8n-480/v8n-640 were runtime-blocked; T2 v8n-640 had no completed full-integer artifact.

The fixed thresholds remained confidence `0.25`, NMS IoU `0.70`, min IoU `0.90`, and max confidence shift `0.20`.
""")

    write("SCOPE24_TFLITE_PI_BENCHMARK.md", f"""# Scope 24 — TFLite Pi benchmark

Status: **NOT RUN — transfer gate blocked**.

Pi identity was verified: `{pi['hardware']['model']}`, `{pi['hardware']['architecture']}`, `{pi['hardware']['ram']}`, throttling `{pi['hardware']['throttled_before']}`. Pi had no installed TFLite/LiteRT runtime, but no dependency was installed because no artifact reached host parity PASS. No Scope 24 directory was created on Pi, no artifact was copied, and no INT8 benchmark was reported.

Scope 21 FP32 NCNN measurements remain the Pi deployment baseline.
""")

    ort_rows = [f"| {x['run_id']} | {x['status']} | {x.get('artifact', {}).get('sha256', 'N/A')} | {x.get('error', 'N/A')} |" for x in ort["records"]]
    write("SCOPE24_ORT_INT8_REPORT.md", """# Scope 24 — ONNX Runtime INT8 secondary report

The single predeclared O1 method was static QDQ INT8, per-channel, MinMax calibration, exact 128-image TRAIN membership. Both generated graphs were rejected by the selected ORT runtime because their bias `DequantizeLinear` nodes used an unsupported `axis` attribute. No QOperator/per-tensor or other permutation was tried.

| Model | Status | Artifact SHA-256 | Error |
|---|---|---|---|
""" + "\n".join(ort_rows) + "\n\nConclusion: `ORT_INT8_BLOCKED`.\n")

    write("SCOPE24_BACKEND_COMPARISON.md", """# Scope 24 — Backend comparison

| Model | Backend/path | Quantized artifact | Host parity | Pi parity | Pi benchmark | Decision |
|---|---|---|---|---|---|---|
| v8n-480 | TFLite T1 | full INT8, invoke blocked | BLOCKED | N/A | N/A | diagnostic-only |
| v8n-480 | TFLite T2 | full INT8, loads | FAIL | N/A | N/A | diagnostic-only |
| v8n-640 | TFLite T1 | full INT8, invoke blocked | BLOCKED | N/A | N/A | diagnostic-only |
| v8n-640 | TFLite T2 | missing after timeout | BLOCKED | N/A | N/A | blocked |
| v8n-480/640 | ORT O1 QDQ | graph generated, runtime invalid | BLOCKED | N/A | N/A | blocked |

No candidate satisfies `INT8_READY_FOR_FREEZE_REVIEW`. No TEST accuracy was used and Scope 21 FP32 Pi measurements were not relabeled.
""")

    write("SCOPE24_TEST_REPORT.md", """# Scope 24 — Test report

Regression guards cover the two-model allowlist, immutable baseline hashes, exact image sizes, TRAIN-only calibration, TEST exclusion, fixed confidence/NMS thresholds, T1/T2 bound, ORT one-variant bound, host-fail transfer prohibition, Pi identity requirement, and no NCNN E4+ experiments.

Commands:

```text
python -m pytest -q
python -m compileall -q scripts src tests
git diff --check
```

No dataset, label, split, tracker, checkpoint, TEST artifact, production detector, or Git history was changed.
""")

    write("SCOPE24_FINAL_REPORT.md", """# Scope 24 — Final report

## Decision

**`PTQ_INT8_PATHS_EXHAUSTED_FOR_CURRENT_SCOPE`**.

Scope 23 NCNN INT8 was already blocked. Scope 24's bounded alternate paths also failed:

- TFLite T1 generated real full-integer artifacts but runtime invocation was blocked by the quantized `LOGISTIC` scale contract.
- TFLite T2 v8n-480 generated a loadable full-integer artifact but failed host parity on fixed-8 and secondary-32; T2 v8n-640 timed out before a complete artifact.
- ORT O1 static QDQ per-channel INT8 generated graphs rejected by ORT because of unsupported `DequantizeLinear axis` attributes.

No alternate artifact was eligible for Pi transfer. Pi 5 access was verified, but no INT8 runtime was installed, no artifact was copied, and no INT8 benchmark was run. Production model freeze was not performed.

The next authorized step is FP32 NCNN production-freeze review. Do not start QAT, 320 training, TEST evaluation, NCNN PTQ brute force, or a third INT8 backend within this scope.

V3 TEST remains locked; `SESSION_DISJOINT` remains UNVERIFIED; checkpoint and split baselines remain unchanged.

Machine-readable summary: [`final_summary.json`](../../../.runtime/scope24/final_summary.json).
""")


if __name__ == "__main__":
    main()
