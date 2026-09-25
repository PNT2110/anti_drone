"""Materialize Scope 18 reports from immutable preflight and run artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/tracking/scope18"
RUNTIME = ROOT / ".runtime/scope18"
LEDGER = RUNTIME / "run_ledger.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def test_commands() -> dict:
    commands = {
        "pytest": ["pytest", "-q"],
        "compileall": ["python", "-m", "compileall", "-q", "scripts", "src", "tests"],
        "git_diff_check": ["git", "diff", "--check"],
    }
    result = {}
    for name, command in commands.items():
        environment = os.environ.copy()
        if name == "pytest":
            # The repository keeps executable helpers in `scripts/` without
            # requiring an installed package; make the root importable in
            # the regression subprocess just as the documented command does.
            environment["PYTHONPATH"] = str(ROOT) + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
        if name == "pytest":
            result[name] = {"command": "PYTHONPATH=. pytest -q", "returncode": completed.returncode, "output": (completed.stdout + completed.stderr)[-4000:]}
            continue
        result[name] = {"command": " ".join(command), "returncode": completed.returncode, "output": (completed.stdout + completed.stderr)[-4000:]}
    return result


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    pre = load(RUNTIME / "label_preflight.json")
    resource = load(RUNTIME / "resource_preflight.json")
    configs = load(RUNTIME / "config_preparation.json")
    ledger = load(LEDGER) if LEDGER.exists() else {"runs": [], "order": []}
    runs = ledger.get("runs", [])
    tests = test_commands()
    now = datetime.now(timezone.utc).isoformat()
    statuses = {run.get("status") for run in runs}
    all_complete = len(runs) == 6 and statuses == {"COMPLETE"}

    input_text = f"""# Scope 18 — Input audit

Generated: `{now}`. Scope: controlled detector training only; no Git commit/push.

## Locked inputs

- Dataset: `{pre['observed_checksums'] and str(ROOT / 'data/processed/drone-single-class-v3-labelrepair-candidate')}`
- Repaired manifest SHA-256: `{pre['observed_checksums']['manifest']}`
- Repaired split registry SHA-256: `{pre['observed_checksums']['split_registry']}`
- Repaired `data.yaml` SHA-256: `{pre['observed_checksums']['data_yaml']}`
- Scope 17 repair audit SHA-256: `{pre['observed_checksums']['repair_audit']}`
- Source mapping: `{ROOT / '.runtime/scope13/rgbt_archive_mapping.csv'}` (SHA-256 `{sha256(ROOT / '.runtime/scope13/rgbt_archive_mapping.csv')}`)
- Original V3 candidate manifest: `{pre['observed_checksums']['v3_manifest']}`
- Original V3 candidate registry: `{pre['observed_checksums']['v3_registry']}`

## Scope boundaries

Only `drone-single-class-v3-labelrepair-candidate` is used. The quarantined 6,505 samples / 4,172 groups are excluded. V1, V2, the original V3 candidate, Scope 15/16 artifacts, tracker/gate code and the V1 checkpoint are not modified. Test is locked and is not used for training or selection. Halmstad remains diagnostic-only and `SPLIT_UNVERIFIED`.

Input audit status: **{pre['status']}**. Config preparation status: **{configs['status']}**.
"""

    label_text = f"""# Scope 18 — Label preflight

Status: **{pre['status']}**

- Samples: `{pre['sample_count']}`
- Split counts: train `{pre['split_counts']['train']}`, val `{pre['split_counts']['val']}`, test `{pre['split_counts']['test']}`
- Class counts: `{json.dumps(pre['class_counts'], sort_keys=True)}`
- Empty labels: `{pre['empty_label_count']}`
- Source objects: `{pre['source_object_count']}`; unresolved: `{pre['source_unresolved_count']}`
- Quarantine leakage: `{pre['quarantine_leakage']}`
- Source-sequence overlap: `{pre['source_sequence_overlap']}`; candidate-prefix overlap: `{pre['candidate_prefix_overlap']}`

The preflight re-read source annotations, verified class `0`, repaired coordinates, split counts, quarantine exclusion, sequence/prefix disjointness, and persisted deterministic seed-42 representative samples for modality, size and boundary categories in `.runtime/scope18/label_preflight.json`.

No test label was used for training or model selection; test remains reserved for a later frozen evaluation.
"""

    resource_text = f"""# Scope 18 — Resource preflight

Status: **{resource['status']}**

- Python: `{resource['python']}`
- PyTorch: `{resource['torch']}`; CUDA runtime `{resource['cuda_version']}`
- Ultralytics: `{resource['ultralytics']}`
- CUDA available: `{resource['cuda_available']}`
- GPU: `{resource['gpu'].get('name')}`, free `{resource['gpu'].get('memory_free_mib')} MiB`, utilization `{resource['gpu'].get('utilization_percent')}%`
- Active training process before launch: `{resource.get('training_started')}`; detected processes: `{len(resource.get('active_scope_processes', []))}`
- Output root existed before launch: `{resource['output_root_exists']}`
- Config count: `{len(resource['configs'])}`

Errors: `{json.dumps(resource['errors'], ensure_ascii=False)}`
"""

    rows = []
    for run in runs:
        attempts = run.get("attempts", [])
        chosen = next((attempt for attempt in attempts if attempt.get("status") == "COMPLETE"), None)
        rows.append(
            f"| {run.get('run_id')} | {run.get('model_id')} | {run.get('imgsz')} | {run.get('status')} | {len(attempts)} | {chosen.get('batch') if chosen else 'N/A'} | {fmt(run.get('best_epoch'))} | {fmt(run.get('best_pt_sha256'))} | {fmt(run.get('last_pt_sha256'))} |"
        )
    matrix_text = """# Scope 18 — Training matrix

Fixed order: YOLOv8n-640, YOLOv8n-480, YOLOv11n-640, YOLOv11n-480, YOLO26n-640, YOLO26n-480. Every run uses epochs=100, seed=42, workers=4, device=0, starting batch=16 with fallback 8 then 4 on OOM only, repaired V3 train/val, and a unique directory below `artifacts/experiments/scope18-v3-labelrepair/`.

| Run | Model | Image size | Status | Attempts | Effective batch | Best epoch | best.pt SHA-256 | last.pt SHA-256 |
|---|---:|---:|---|---:|---:|---:|---|---|
""" + "\n".join(rows) + "\n"

    validation_parts = ["# Scope 18 — Validation results\n", "Validation is from the V3 `val` split only. No test inference, test scoring, model selection or threshold tuning was performed.\n"]
    for run in runs:
        validation_parts.append(f"## `{run.get('run_id')}` — {run.get('status')}\n")
        validation_parts.append(f"- Best epoch: `{fmt(run.get('best_epoch'))}`\n- Metrics: `{json.dumps(run.get('validation_metrics', {}), sort_keys=True)}`\n- test_used: `{run.get('test_used')}`\n")
    validation_text = "\n".join(validation_parts)

    oom_lines = ["# Scope 18 — Resume/OOM report\n", "The launcher permits fallback only after an actual OOM, keeps each attempt in a unique directory, and does not resume from `best.pt`. Resume is allowed only from an exact-run `last.pt` contract (run/model/imgsz/dataset/seed/effective batch).\n", "| Run | Attempt | Batch | Status | Duration (s) |\n|---|---|---:|---|---:|"]
    for run in runs:
        for attempt in run.get("attempts", []):
            oom_lines.append(f"| {run.get('run_id')} | {Path(attempt.get('path', '')).name} | {attempt.get('batch')} | {attempt.get('status')} | {fmt(attempt.get('duration_seconds'))} |")
    if not any(attempt.get("status") == "OOM" for run in runs for attempt in run.get("attempts", [])):
        oom_lines.append("\nNo OOM event was recorded; therefore no batch fallback or resume was needed.")
    oom_text = "\n".join(oom_lines) + "\n"

    test_text = "# Scope 18 — Test report\n\n" + json.dumps(tests, indent=2, ensure_ascii=False) + "\n"
    final_status = "TRAINING_COMPLETE" if all_complete else ("PARTIALLY_COMPLETE" if runs else "TRAINING_NOT_COMPLETE")
    final_text = f"""# Scope 18 — Final report

Status: **{final_status}**

The controlled training matrix was executed against the label-repaired V3 candidate only. Run statuses: `{json.dumps([run.get('status') for run in runs])}`. The ledger is `{LEDGER}`.

This scope does not select a production model, does not claim generalization, does not compute independent test metrics, and does not alter `SPLIT_UNVERIFIED`. Test remains locked. Halmstad remains diagnostic-only. No detector retraining outside the six declared runs, tracker/gate modification, dataset reshuffle, Pi/camera access, or Git commit/push is authorized by this report.

Detailed artifacts:

- [Input audit](SCOPE18_INPUT_AUDIT.md)
- [Label preflight](SCOPE18_LABEL_PREFLIGHT.md)
- [Resource preflight](SCOPE18_RESOURCE_PREFLIGHT.md)
- [Training matrix](SCOPE18_TRAINING_MATRIX.md)
- [Validation results](SCOPE18_VALIDATION_RESULTS.md)
- [Resume/OOM report](SCOPE18_RESUME_OOM_REPORT.md)
- [Test report](SCOPE18_TEST_REPORT.md)
"""
    files = {
        "SCOPE18_INPUT_AUDIT.md": input_text,
        "SCOPE18_LABEL_PREFLIGHT.md": label_text,
        "SCOPE18_RESOURCE_PREFLIGHT.md": resource_text,
        "SCOPE18_TRAINING_MATRIX.md": matrix_text,
        "SCOPE18_VALIDATION_RESULTS.md": validation_text,
        "SCOPE18_RESUME_OOM_REPORT.md": oom_text,
        "SCOPE18_TEST_REPORT.md": test_text,
        "SCOPE18_FINAL_REPORT.md": final_text,
    }
    for name, text in files.items():
        (DOCS / name).write_text(text, encoding="utf-8")
    print(json.dumps({"status": final_status, "reports": [str(DOCS / name) for name in files]}, indent=2, ensure_ascii=False))
    return 0 if all_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
