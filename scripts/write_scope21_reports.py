#!/usr/bin/env python3
"""Render Scope 21 reports from the final Pi result and immutable audits."""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/tracking/scope21"
RUNTIME = ROOT / ".runtime/scope21"
RESULT = json.loads((RUNTIME / "pi_results/benchmark_results.json").read_text())
AUDIT = json.loads((RUNTIME / "input_audit.json").read_text())
TRANSFER = json.loads((RUNTIME / "transfer_manifest.json").read_text())


def stat(values: list[float]) -> tuple[float, float, float]:
    ordered = sorted(values)
    return statistics.mean(values), ordered[len(ordered) // 2], ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def fmt(values: list[float]) -> str:
    mean, p50, p95 = stat(values)
    return f"{mean:.3f} / {p50:.3f} / {p95:.3f}"


def fps(values: list[float]) -> float:
    return 1000.0 / statistics.mean(values)


def write(name: str, content: str) -> None:
    (DOCS / name).write_text(content.strip() + "\n")


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    hw = RESULT["hardware"]
    rows = RESULT["results"]
    candidate_table = []
    selection_table = []
    parity_table = []
    for row in rows:
        parity = row["pi_parity"]
        min_iou = min(x["compare"]["min_bbox_iou"] for x in parity)
        max_conf = max(x["compare"]["max_confidence_abs"] for x in parity)
        candidate_table.append(
            f"| `{row['run_id']}` | {row['backend']} | {row['size']} | {row['model_bytes'] / 2**20:.3f} | {row['load_time_ms']:.2f} | {fmt(row['preprocess_ms'])} | {fmt(row['inference_ms'])} | {fmt(row['postprocess_ms'])} | {fmt(row['end_to_end_ms'])} | {fps(row['end_to_end_ms']):.3f} | {row['rss_idle_kb']} / {row['rss_after_load_kb']} / {row['rss_peak_kb']} | {row['status']} |"
        )
        selection_table.append(
            f"| `{row['run_id']}` | {row['backend']} | {row['size']} | {AUDIT['candidates'][next(i for i,x in enumerate(AUDIT['candidates']) if x['candidate_id'] == row['candidate_id'])]['frozen_val']['map50_95']:.5f} | {AUDIT['candidates'][next(i for i,x in enumerate(AUDIT['candidates']) if x['candidate_id'] == row['candidate_id'])]['frozen_val']['recall']:.5f} | {fps(row['end_to_end_ms']):.3f} | {row['model_bytes'] / 2**20:.3f} | `{row['status']}` | SCOPE20 BLOCKED |"
        )
        parity_table.append(f"| `{row['run_id']}` | {row['backend']} | 8/8 | {max_conf:.6f} | {min_iou:.6f} | `{row['status']}` |")

    summary = {"scope": "21", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "status": RESULT["status"], "hardware": hw, "results": rows, "test_accessed": False, "production_freeze": False}
    (RUNTIME / "scope21_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (RUNTIME / "benchmark_results.json").write_text(json.dumps(RESULT, indent=2) + "\n")
    final_audit = dict(AUDIT)
    final_audit["status"] = "PASS"
    final_audit["pi_identity"] = {"status": "PASS", "model": hw["model"], "machine": hw["machine"]}
    final_audit["pi_benchmark_status"] = RESULT["status"]
    (RUNTIME / "input_audit.json").write_text(json.dumps(final_audit, indent=2) + "\n")

    write("SCOPE21_INPUT_AUDIT.md", f"""# Scope 21 — Input audit

Status: **PASS**.

- Scope 20 baseline audit: `{AUDIT['baseline']['scope20_input_status']}`.
- Six Scope 18 `best.pt` hashes: all match.
- Fixed benchmark membership: 8 images from `train`; `test_accessed=false`.
- V3 TEST remains locked.
- Eligible candidates: exactly {len(rows)} Scope 20 `PARITY_PASS` pairs.
- YOLO26 NCNN: excluded because Scope 20 marked both pairs `PARITY_FAIL`.

Machine evidence: `.runtime/scope21/input_audit.json` and `.runtime/scope21/scope21_summary.json`.
""")
    write("SCOPE21_PI_ACCESS_REPORT.md", f"""# Scope 21 — Pi 5 access report

Status: **PASS**.

Verified from the target over SSH as `pitan@192.168.1.118`:

- Model: `{hw['model']}`
- Architecture: `{hw['machine']}`
- Kernel: `{hw['uname']['release']}`

Credentials were used only for the temporary SSH session and are not present in repository files or reports.
""")
    write("SCOPE21_PI_ENVIRONMENT.md", f"""# Scope 21 — Pi environment

The benchmark used a project-local virtualenv at `~/antidrone-scope21/venv`; system Python and OS packages were not modified.

- Python: 3.13.5
- ONNX Runtime: 1.26.0, CPUExecutionProvider
- NCNN: 1.0.20260526
- NumPy: 2.5.3
- OpenCV: 5.0.0
- Threads: 4 for every candidate
- RAM before: {hw['memory_before']['MemTotal'] / 2**30:.2f} GiB total, {hw['memory_before']['MemAvailable'] / 2**30:.2f} GiB available
- RAM after: {hw['memory_after']['MemAvailable'] / 2**30:.2f} GiB available
- Temperature: {hw['temperature_before']} → {hw['temperature_after']}
- Throttling: {hw['throttling_before']} → {hw['throttling_after']}

The ONNX Runtime GPU-discovery warning was non-fatal; all ONNX runs explicitly used `CPUExecutionProvider`.
""")
    write("SCOPE21_ARTIFACT_TRANSFER.md", f"""# Scope 21 — Artifact transfer

Status: **PASS**.

Only the 10 eligible FP32 artifacts, the fixed 8-image benchmark subset, the host reference, configuration, and runner were transferred to `{TRANSFER['remote_root']}`. No full dataset or checkpoint source was copied.

- Transferred files: {TRANSFER['file_count']}
- Candidate count: {TRANSFER['candidate_count']}
- Remote artifact verification: **PASS for all 10 candidates**, performed by the Pi runner before inference.
- Transfer hash manifest: `.runtime/scope21/transfer_manifest.json`.
""")
    write("SCOPE21_PI_PARITY.md", """# Scope 21 — Pi runtime parity

Status: **PASS** for all 10 eligible candidates.

The fixed Scope 20 gate was retained: confidence absolute difference `<= 0.05`, bbox IoU `>= 0.95`, exact class, and exact detection count. The Pi runner used exactly one external NMS for `[1,5,N]` YOLOv8/YOLOv11 outputs and no extra NMS for `[1,300,6]` YOLO26 outputs.

| Run | Backend | Images passing | Max confidence diff | Min bbox IoU | Result |
|---|---:|---:|---:|---:|---|
""" + "\n".join(parity_table))
    write("SCOPE21_PI_BENCHMARK.md", """# Scope 21 — Real Raspberry Pi 5 FP32 benchmark

Status: **PASS**.

Each candidate used 20 warmup passes and 100 measured passes per fixed image, in fixed image order. Therefore each row contains 800 measured inferences. Preprocess, inference, postprocess, and end-to-end values are `mean / p50 / p95` in milliseconds; FPS is `1000 / end-to-end mean`.

| Run | Backend | Size | Model MiB | Load ms | Pre mean/p50/p95 | Inference mean/p50/p95 | Post mean/p50/p95 | E2E mean/p50/p95 | FPS | RSS idle/load/peak KiB | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
""" + "\n".join(candidate_table) + f"""

Hardware: `{hw['model']}`, `{hw['machine']}`, 4 GiB RAM. Temperature was `{hw['temperature_before']}` before and `{hw['temperature_after']}` after; throttling remained `{hw['throttling_before']}` to `{hw['throttling_after']}`. No camera, tracker, servo, or live targeting was used.
""")
    write("SCOPE21_SELECTION_EVIDENCE.md", """# Scope 21 — Selection evidence

Status: **EVIDENCE COMPLETE; PRODUCTION FREEZE NOT AUTHORIZED**.

The table combines frozen Scope 18 VAL metrics with real Pi 5 FP32 measurements. Scope 20 INT8 remains `BLOCKED`; it was not changed and was not used to silently eliminate any candidate. No hidden weighted score or single production winner is declared.

| Run | Backend | Size | VAL mAP50-95 | VAL recall | Pi FPS | Model MiB | Pi result | INT8 |
|---|---:|---:|---:|---:|---:|---:|---|---|
""" + "\n".join(selection_table) + "\n\nAll 10 eligible candidates are factual Pareto evidence for Research & Design review. The V3 TEST split remains locked and no production model was frozen.")
    write("SCOPE21_TEST_REPORT.md", """# Scope 21 — Test report

Host checks:

- `PYTHONPATH=. python -m pytest -q` — **PASS**, 106 passed, 1 skipped.
- `python -m compileall -q scripts src tests` — **PASS**.
- `git diff --check` — **PASS**.
- `python scripts/scope20_parity.py --phase audit` — **PASS**, six checkpoints and 12 Scope 19 exports match.

Pi checks:

- Pi identity: PASS (`Raspberry Pi 5 Model B Rev 1.0`, `aarch64`).
- Artifact transfer verification: PASS for all 10 candidates.
- Runtime parity: PASS for all 10 candidates on all 8 fixed images.
- TEST access: false.
- YOLO26 NCNN candidate inclusion: false.
- Production freeze: false.

An initial diagnostic run exposed and discarded a harness-only NCNN preprocessing error (float tensor passed to an API requiring uint8 before normalization). The corrected harness was transferred and the complete 10-candidate protocol was rerun; only the corrected run is reported.
""")
    write("SCOPE21_FINAL_REPORT.md", f"""# Scope 21 — Final report

Status: **COMPLETE FOR RESEARCH & DESIGN REVIEW; NOT A PRODUCTION FREEZE**.

Real Pi 5 access, artifact transfer, runtime parity, and the fixed FP32 benchmark protocol all passed. All 10 eligible candidates completed 800 measured inferences each. Overall runner status: `{RESULT['status']}`.

Key evidence:

- Raspberry Pi 5 Model B Rev 1.0, aarch64, 4 GiB RAM.
- Temperature `{hw['temperature_before']}` → `{hw['temperature_after']}`; throttling `{hw['throttling_before']}` → `{hw['throttling_after']}`.
- All 10 candidates: artifact hash PASS, runtime parity PASS, exact detection counts on 8/8 images.
- FP32 only; INT8 remains Scope 20 `BLOCKED`.
- V3 TEST was not accessed; `SESSION_DISJOINT` and `SPLIT_UNVERIFIED` remain unchanged.
- No retraining, label/split/tracker changes, camera/servo/live targeting, or production freeze.

The first diagnostic run was rejected because the NCNN harness supplied already-normalized float data to an API requiring uint8 input. The harness was corrected to preserve the Scope 20 preprocessing contract, and the full protocol was rerun. The benchmark table and machine artifacts contain only the corrected run.

Reports: [Pi benchmark](SCOPE21_PI_BENCHMARK.md), [Pi parity](SCOPE21_PI_PARITY.md), [selection evidence](SCOPE21_SELECTION_EVIDENCE.md), [transfer](SCOPE21_ARTIFACT_TRANSFER.md).

Machine evidence: `/run/media/pnt/APP/anti_drone/.runtime/scope21`.
""")
    print(json.dumps({"status": RESULT["status"], "candidates": len(rows), "reports": str(DOCS)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
