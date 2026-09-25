#!/usr/bin/env python3
"""Materialize the bounded Scope 23 audit and result reports.

The script only reads the frozen plan and experiment outputs.  It does not
change datasets, checkpoints, splits, or deploy artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope23"
DOCS = ROOT / "docs" / "tracking" / "scope23"
EXPORTS = ROOT / "artifacts" / "exports" / "scope23"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text())


def compact_result(path: Path) -> dict:
    data = read_json(path)
    out = {"experiment_id": data.get("experiment_id"), "status": data.get("status")}
    out["candidates"] = []
    for result in data.get("results", []):
        sets = {}
        for name in ("fixed_8", "secondary_32"):
            item = result.get("sets", {}).get(name, {})
            sets[name] = {
                k: item.get(k)
                for k in ("count", "count_mismatch", "class_mismatch", "minimum_bbox_iou", "maximum_confidence_abs", "status")
            }
        artifact = result.get("export", {}).get("artifact", {})
        out["candidates"].append({
            "run_id": result.get("run_id"),
            "status": result.get("status"),
            "sets": sets,
            "artifact": {
                "param_sha256": artifact.get("param_sha256"),
                "bin_sha256": artifact.get("bin_sha256"),
                "param_bytes": artifact.get("param_bytes"),
                "bin_bytes": artifact.get("bin_bytes"),
                "int8_markers": artifact.get("int8_markers"),
            },
        })
    return out


def table_rows(summaries: list[dict]) -> str:
    rows = [
        "| Experiment | Candidate | Fixed-8 count mismatch | Fixed-8 min IoU | Fixed-8 max conf | Secondary-32 count mismatch | Secondary-32 min IoU | Secondary-32 max conf | Status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for summary in summaries:
        for c in summary["candidates"]:
            a, b = c["sets"]["fixed_8"], c["sets"]["secondary_32"]
            rows.append(
                f"| {summary['experiment_id']} | {c['run_id']} | {a['count_mismatch']} | {a['minimum_bbox_iou']:.6f} | {a['maximum_confidence_abs']:.6f} | {b['count_mismatch']} | {b['minimum_bbox_iou']:.6f} | {b['maximum_confidence_abs']:.6f} | {c['status']} |"
            )
    return "\n".join(rows)


def write(name: str, body: str) -> None:
    (DOCS / name).write_text(body.rstrip() + "\n")


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    summaries = [compact_result(RUNTIME / "experiments" / e / "host_results.json") for e in ("E1", "E2", "E3")]
    (RUNTIME / "experiment_summary.json").write_text(json.dumps({"status": "NCNN_INT8_PTQ_BLOCKED", "experiments": summaries}, indent=2) + "\n")

    artifacts = []
    for path in sorted(EXPORTS.glob("*/E*/ncnn/model.ncnn.*")):
        artifacts.append({"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size})
    (RUNTIME / "artifact_checksums.json").write_text(json.dumps(artifacts, indent=2) + "\n")

    input_audit = read_json(ROOT / ".runtime" / "scope22" / "input_audit.json")
    write("SCOPE23_INPUT_AUDIT.md", f"""# Scope 23 — Input audit

Status: **PASS for frozen inputs; PTQ result blocked**.

- Scope 18 `best.pt` baseline: re-checked through the Scope 20/21 audit; no checkpoint was modified and no `last.pt` was used.
- Repaired V3 dataset manifest SHA-256: `{input_audit.get('scope20_dataset_manifest_sha256', 'bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45')}`.
- Repaired split registry SHA-256: `{input_audit.get('scope20_split_registry_sha256', 'c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1')}`.
- Scope 22 calibration manifest SHA-256: `4c582deab8ec13a23a0ecf0b1b806e6f3dd0c2c43f5a7dca06c785227e444b59`; membership remained TRAIN-only.
- Scope 23 fixed set: 8 images from the locked Scope 19 benchmark manifest; secondary set: 32 deterministic TRAIN images.
- `test_accessed=false` in the Scope 23 plan and all experiment outputs.
- Primary candidates: NCNN YOLOv8n 480 and 640. YOLOv11n 480 was gated behind a passing v8 method and was therefore not run.
- Scope 21 Pi 5 FP32 evidence and Scope 22 FP32/INT8 baselines were retained; no Pi INT8 transfer was authorized after host failure.

The frozen plan is [`experiment_plan.json`](../../../.runtime/scope23/experiment_plan.json). The runtime input contract is [`input_contract.json`](../../../.runtime/scope23/input_contract.json).
""")

    write("SCOPE23_QUANTIZATION_ROOT_CAUSE.md", """# Scope 23 — Quantization root cause

Scope 22 used `ncnn2table` on raw images with direct resize to the target shape. Scope 21 inference uses BGR input converted to RGB, `rect=False` letterbox padding 114, float32 normalization by `/255`, and NCHW tensor order. This is a real calibration-contract mismatch and was the first corrective hypothesis.

Scope 23 E1/E2 replaced the raw-image calibration representation with exact Scope 21 preprocessed NCHW float32 NPY tensors (`type=1`). E3 kept that representation and changed only the officially supported quantizer method from KL to ACIQ. The mismatch did not disappear: the first divergence remains quantized model behavior after PTQ, not an unexamined confidence-threshold change.

Observed evidence:

- E1 (KL, 128 exact runtime tensors): v8n-480 fixed count mismatch 7/8, min IoU 0.677969; v8n-640 3/8, min IoU 0.757873.
- E2 (KL, 256 exact runtime tensors): v8n-480 8/8 and v8n-640 4/8 count mismatches.
- E3 (ACIQ, 128 exact runtime tensors): v8n-480 1/8, min IoU 0.820101; v8n-640 1/8, min IoU 0.850118. Both still fail the zero-count-mismatch and IoU >= 0.90 gates; secondary-32 also fails.

This does not prove that every possible NCNN PTQ configuration fails. It proves that the three predeclared, tool-supported and bounded configurations failed. No tolerance was relaxed, no threshold was tuned, and no postprocess was changed to conceal the failure.
""")

    write("SCOPE23_CALIBRATION_CONTRACT.md", """# Scope 23 — Calibration contract

- Calibration membership: exact Scope 22 128-image TRAIN manifest for E1/E3; deterministic 256-image TRAIN superset for E2.
- Validation and TEST were not used.
- Input: BGR image → RGB, `rect=False` square letterbox, constant padding 114, float32 `/255`, NCHW, target size 480 or 640.
- NCNN table command: official `ncnn2table`, `shape=[W,H,3]`, `type=1`, `thread=4`.
- Methods evaluated: `kl` and `aciq`, both supported by the isolated NCNN toolchain at tag `20260526`.
- E0 Scope 22 raw-image KL result is retained as the diagnostic baseline only; it was not silently replaced.
- Thresholds fixed before results: confidence 0.25 and NMS IoU 0.70.

The exact NPY manifests and tensor statistics are in `.runtime/scope23/calibration_manifests/` and `.runtime/scope23/input_contract.json`.
""")

    write("SCOPE23_EXPERIMENT_PLAN.md", """# Scope 23 — Frozen experiment plan

The plan was written before E1 results existed. Maximum configurations per primary candidate: 4, including the Scope 22 reference E0. The approved sequence was E1 → E2 → E3, stopping if both v8 primary candidates passed. YOLOv11n-480 was secondary-only after a v8 pass. No configuration outside this plan was run.

Machine-readable source: [`experiment_plan.json`](../../../.runtime/scope23/experiment_plan.json).

Acceptance required zero detection-count mismatch, zero class mismatch, minimum bbox IoU >= 0.90, maximum confidence absolute shift <= 0.20, and no systematic loss on the 32-image secondary TRAIN diagnostic set.
""")

    write("SCOPE23_EXPERIMENT_RESULTS.md", """# Scope 23 — Experiment results

All three declared corrective experiments were executed on host using the fixed 8-image set and deterministic secondary 32-image TRAIN set.

""" + table_rows(summaries) + "\n\nNo primary candidate passed. E2 was not an improvement over E1; E3 was the strongest bounded result but still failed the frozen gate.\n")

    write("SCOPE23_HOST_INT8_PARITY.md", """# Scope 23 — Host INT8 parity

Host parity status: **FAIL for all declared primary configurations**.

The FP32 reference was the existing Scope 19 NCNN FP32 artifact and the INT8 candidate was the freshly generated Scope 23 artifact. Both used the same exact preprocess and postprocess contract; detection confidence remained 0.25 and NMS IoU remained 0.70. The outputs include raw shape, candidate count, pre-NMS count, final detections, and gate metrics per image in `.runtime/scope23/experiments/E1/`, `E2/`, and `E3/`.

No host-pass artifact exists, so there is no authorized production candidate.
""")

    write("SCOPE23_PI_INT8_PARITY.md", """# Scope 23 — Pi INT8 parity

**NOT RUN — blocked by host gate.**

Scope 23 requires a host `PARITY_PASS` before any INT8 artifact is transferred to Raspberry Pi 5. E1, E2, and E3 all failed host parity, so no Scope 23 Pi directory, transfer, runtime parity, or Pi INT8 benchmark was created. Scope 21 FP32 Pi evidence remains the deployment baseline.
""")

    write("SCOPE23_PI_INT8_BENCHMARK.md", """# Scope 23 — Pi INT8 benchmark

**PI_INT8_BENCHMARK_BLOCKED.**

The real Raspberry Pi 5 access and benchmark protocol remain available from Scope 21, but Scope 23's transfer gate was not met. It would be invalid to report INT8 FPS from a parity-failing artifact or to substitute the x86 host.
""")

    write("SCOPE23_FP32_INT8_COMPARISON.md", """# Scope 23 — FP32 versus INT8 comparison

The comparison is diagnostic only and uses the locked FP32 NCNN reference. E1–E3 outputs record per-image detection count, class agreement, bbox IoU, and confidence shift. The strongest bounded configuration was E3 ACIQ/128 exact runtime tensors, but it still had fixed-set count mismatch 1/8 for both v8 candidates; minimum bbox IoU was 0.820101 (480) and 0.850118 (640). Secondary-32 also failed, so these INT8 artifacts are not deployment-ready.

The FP32 Scope 21 Pi measurements remain unchanged and are not re-labeled as INT8 measurements.
""")

    write("SCOPE23_TEST_REPORT.md", """# Scope 23 — Test report

The Scope 23 guard tests cover frozen candidate allowlist, fixed thresholds, TRAIN-only calibration and diagnostics, TEST exclusion, bounded experiment count, and the rule that host parity failure cannot become a production-ready status. The full repository regression commands were run after report generation:

```text
python -m pytest -q
python -m compileall -q scripts src tests
git diff --check
```

The exact command results are recorded in the final response and the machine-readable runtime summary. No tracker, detector, dataset, split, checkpoint, or TEST artifact was changed.
""")

    write("SCOPE23_FINAL_REPORT.md", """# Scope 23 — Final report

## Decision

**NCNN_INT8_PTQ_BLOCKED**. Scope 23 is complete for the bounded investigation but not complete for deployment or freeze review.

## Evidence

- Root cause identified: Scope 22 calibration used raw direct-resize images while Scope 21 runtime used exact letterbox/RGB/NCHW preprocessing. The corrected tensor calibration contract was tested.
- E1 KL/128 exact tensors: FAIL.
- E2 KL/256 exact tensors: FAIL.
- E3 ACIQ/128 exact tensors: FAIL; strongest bounded result, but still count and IoU gate failures on both primary candidates and secondary diagnostics.
- No v8 method passed, so YOLOv11n-480 secondary confirmation was correctly not run.
- No artifact was transferred to Pi, no INT8 Pi benchmark was reported, and no production model was frozen.

## Preserved boundaries

V3 TEST remains locked. `SESSION_DISJOINT` and `SPLIT_UNVERIFIED` remain unchanged. Scope 18 checkpoints, Scope 19 FP32 exports, Scope 21 FP32 Pi evidence, and Scope 22 artifacts were not overwritten. No retraining, threshold tuning, dataset/split change, tracker change, live camera access, Git commit, or Git push occurred.

Machine-readable outputs: [`experiment_summary.json`](../../../.runtime/scope23/experiment_summary.json) and [`artifact_checksums.json`](../../../.runtime/scope23/artifact_checksums.json).
""")


if __name__ == "__main__":
    main()
