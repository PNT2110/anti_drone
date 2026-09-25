"""Run the six Scope 18 detector experiments sequentially.

The runner is intentionally conservative: it validates immutable inputs before
each run, never passes a test split to the training call, keeps every OOM
attempt, and uses a new attempt directory for each batch fallback.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import platform
import random
import subprocess
import time
import traceback
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs/training/scope18"
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
OUTPUT_ROOT = ROOT / "artifacts/experiments/scope18-v3-labelrepair"
RUNTIME = ROOT / ".runtime/scope18"
ORDER = [("yolov8n", 640), ("yolov8n", 480), ("yolov11n", 640), ("yolov11n", 480), ("yolo26n", 640), ("yolo26n", 480)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state() -> dict:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
        except Exception:
            return "unavailable"
    return {"head": run("rev-parse", "HEAD"), "branch": run("branch", "--show-current"), "status_short": run("status", "--short")}


def gpu_state() -> dict:
    try:
        raw = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu", "--format=csv,noheader,nounits"], text=True).strip().splitlines()[0]
        name, total, used, free, util = [part.strip() for part in raw.split(",")]
        return {"name": name, "memory_total_mib": int(total), "memory_used_mib": int(used), "memory_free_mib": int(free), "utilization_percent": int(util)}
    except Exception as exc:
        return {"error": str(exc)}


def install_channel_dropout(model: YOLO, probability: float) -> list:
    if probability <= 0:
        return []
    feature_indices = [i for i, _layer in enumerate(model.model.model) if i < len(model.model.model) - 1]
    selected = feature_indices[-8:-2]
    handles = []
    dropouts = []

    def hook_factory():
        dropout = torch.nn.Dropout2d(p=probability)
        dropouts.append(dropout)

        def hook(module, _inputs, output):
            if module.training and isinstance(output, torch.Tensor) and output.ndim == 4:
                return dropout(output)
            return output

        return hook

    for index in selected:
        handles.append(model.model.model[index].register_forward_hook(hook_factory()))
    return handles


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def checkpoint_summary(run_dir: Path) -> dict:
    results = run_dir / "results.csv"
    summary = {"results_csv": str(results), "results_csv_sha256": sha256(results) if results.is_file() else None, "epoch_count": 0, "best_epoch": None, "validation_metrics": {}}
    if not results.is_file():
        return summary
    with results.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    summary["epoch_count"] = len(rows)
    if not rows:
        return summary
    metric_keys = ["metrics/precision(B)", "metrics/recall(B)", "metrics/mAP50(B)", "metrics/mAP50-95(B)"]
    for key in metric_keys:
        values = []
        for row in rows:
            try:
                values.append(float(row[key]))
            except (KeyError, TypeError, ValueError):
                pass
        if values:
            summary["validation_metrics"][key] = {"final": values[-1], "best": max(values)}
    map_key = "metrics/mAP50-95(B)"
    if map_key in rows[0]:
        valid = [(float(row[map_key]), index + 1) for index, row in enumerate(rows) if row.get(map_key, "") not in ("", None)]
        if valid:
            summary["best_epoch"] = max(valid)[1]
    return summary


def run_one(config: dict) -> dict:
    run_id = config["run_id"]
    run_dir = OUTPUT_ROOT / run_id
    config_path = CONFIG_DIR / f"{run_id}.json"
    record = {
        "run_id": run_id,
        "model_id": config["model_id"],
        "imgsz": config["imgsz"],
        "status": "RUNNING",
        "dataset_path": str(DATASET),
        "dataset_manifest_sha256": sha256(DATASET / "manifest.json"),
        "dataset_split_registry_sha256": sha256(DATASET / "split_registry.json"),
        "data_yaml_sha256": sha256(DATASET / "data.yaml"),
        "repair_audit_sha256": sha256(ROOT / ".runtime/scope17/label_repair_audit.json"),
        "config_sha256": sha256(config_path),
        "source_mapping_reference": str(ROOT / ".runtime/scope13/rgbt_archive_mapping.csv"),
        "starting_weight_path": config["starting_weight_path"],
        "starting_weight_sha256": sha256(Path(config["starting_weight_path"])),
        "seed": config["seed"],
        "epochs": config["epochs"],
        "workers": config["workers"],
        "batch_policy": config["batch_fallback_policy"],
        "optimizer": config["optimizer"],
        "augmentation": config["augmentation"],
        "channel_dropout": config["channel_dropout"],
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "git": git_state(),
        "test_used": False,
        "attempts": [],
    }
    if run_dir.exists():
        record["status"] = "BLOCKED_OUTPUT_EXISTS"
        record["error"] = f"Refusing to overwrite {run_dir}"
        return record
    run_dir.mkdir(parents=True, exist_ok=True)
    for batch in config["batch_fallback_policy"]:
        attempt_dir = run_dir / f"attempt-batch{batch}"
        if attempt_dir.exists():
            record["attempts"].append({"batch": batch, "status": "BLOCKED_OUTPUT_EXISTS", "path": str(attempt_dir)})
            continue
        started = time.time()
        attempt = {"batch": batch, "status": "RUNNING", "path": str(attempt_dir), "started_at_unix": started, "gpu_before": gpu_state(), "effective_config": config | {"effective_batch": batch, "run_directory": str(attempt_dir), "test_used": False}}
        write_json(run_dir / f"attempt-batch{batch}.preflight.json", attempt)
        random.seed(config["seed"])
        np.random.seed(config["seed"])
        torch.manual_seed(config["seed"])
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(config["seed"])
            torch.cuda.reset_peak_memory_stats()
        handles = []
        model = None
        try:
            model = YOLO(config["starting_weight_path"])
            handles = install_channel_dropout(model, config["channel_dropout"]["probability"])
            train_kwargs = dict(
                data=str(DATASET / "data.yaml"), epochs=config["epochs"], imgsz=config["imgsz"], batch=batch,
                workers=config["workers"], device=config["device"], seed=config["seed"], deterministic=True,
                amp=True, cache=False, patience=config["patience"], pretrained=True,
                project=str(run_dir), name=f"attempt-batch{batch}", exist_ok=False, plots=True, verbose=True,
            )
            # No split/test argument is passed: Ultralytics training consumes
            # train and val only; Scope 18 never invokes test evaluation.
            model.train(**train_kwargs)
            save_dir = Path(getattr(getattr(model, "trainer", None), "save_dir", attempt_dir))
            best = save_dir / "weights/best.pt"
            last = save_dir / "weights/last.pt"
            attempt.update({"status": "COMPLETE" if best.is_file() and last.is_file() else "FAILED_CHECKPOINT", "save_dir": str(save_dir), "best_pt": str(best), "last_pt": str(last), "best_pt_sha256": sha256(best) if best.is_file() else None, "last_pt_sha256": sha256(last) if last.is_file() else None, "checkpoint_summary": checkpoint_summary(save_dir), "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None})
        except RuntimeError as exc:
            text = str(exc)
            attempt.update({"status": "OOM" if "out of memory" in text.lower() or "cuda error" in text.lower() and "memory" in text.lower() else "FAILED", "error": text, "traceback": traceback.format_exc()})
        except Exception as exc:
            attempt.update({"status": "FAILED", "error": str(exc), "traceback": traceback.format_exc()})
        finally:
            for handle in handles:
                handle.remove()
            attempt["ended_at_unix"] = time.time()
            attempt["duration_seconds"] = attempt["ended_at_unix"] - started
            attempt["gpu_after"] = gpu_state()
            attempt_dir.mkdir(parents=True, exist_ok=True)
            write_json(attempt_dir / "attempt_provenance.json", attempt)
            record["attempts"].append(attempt)
            del model
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        if attempt["status"] == "COMPLETE":
            record["status"] = "COMPLETE"
            record["selected_attempt"] = str(attempt_dir)
            record["best_pt_sha256"] = attempt.get("best_pt_sha256")
            record["last_pt_sha256"] = attempt.get("last_pt_sha256")
            record["validation_metrics"] = attempt.get("checkpoint_summary", {}).get("validation_metrics", {})
            record["best_epoch"] = attempt.get("checkpoint_summary", {}).get("best_epoch")
            break
        if attempt["status"] != "OOM":
            record["status"] = attempt["status"]
            break
    if record["status"] == "RUNNING":
        record["status"] = "BLOCKED_OOM"
    record["ended_at_unix"] = time.time()
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None, help="Optional run IDs; default is all six in fixed order")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("BLOCKED: CUDA unavailable")
    if not (DATASET / "data.yaml").is_file():
        raise RuntimeError("BLOCKED: repaired data.yaml missing")
    configs = {f"scope18-{model_id}-{imgsz}": json.loads((CONFIG_DIR / f"scope18-{model_id}-{imgsz}.json").read_text(encoding="utf-8")) for model_id, imgsz in ORDER}
    selected = [f"scope18-{model_id}-{imgsz}" for model_id, imgsz in ORDER if args.only is None or f"scope18-{model_id}-{imgsz}" in args.only]
    RUNTIME.mkdir(parents=True, exist_ok=True)
    ledger_path = RUNTIME / "run_ledger.json"
    ledger = {"scope": "scope18", "dataset": str(DATASET), "test_used": False, "order": selected, "runs": []}
    write_json(ledger_path, ledger)
    for run_id in selected:
        config = configs[run_id]
        # Recheck immutable inputs before every run.
        if sha256(DATASET / "manifest.json") != config["dataset_manifest_sha256"] or sha256(DATASET / "split_registry.json") != config["dataset_split_registry_sha256"] or sha256(ROOT / ".runtime/scope17/label_repair_audit.json") != config["repair_audit_sha256"]:
            result = {"run_id": run_id, "status": "INPUT_CHANGED", "test_used": False}
        else:
            result = run_one(config)
        ledger["runs"].append(result)
        write_json(ledger_path, ledger)
        print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
    return 0 if all(item["status"] == "COMPLETE" for item in ledger["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
