"""Evaluate and export the completed fresh training matrix.

The server copy waits for matrix_manifest.json, evaluates every best.pt on the
locked test split, selects by validation mAP50-95, and exports ONNX/NCNN/TFLite.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import time
import traceback
from pathlib import Path

from ultralytics import YOLO


DATA = Path(os.environ.get("FPV_DATA", "/mnt/home_big/pnt/anti_drone_data/data_train"))
RUN_ROOT = Path(
    os.environ.get(
        "FPV_RUN_ROOT",
        "/mnt/home_big/pnt/anti_drone_data/training_runs/fresh_matrix",
    )
)
DEPLOY_ROOT = Path(
    os.environ.get("FPV_DEPLOY_ROOT", "/mnt/home_big/pnt/anti_drone_data/deployment")
)
WEB_MODELS = Path(os.environ.get("FPV_WEB_MODELS", "/home/pnt/drone_web/models"))
MANIFEST = RUN_ROOT / "matrix_manifest.json"
STATUS = DEPLOY_ROOT / "deployment_manifest.json"


def write_status(value: dict) -> None:
    DEPLOY_ROOT.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(value, indent=2), encoding="utf-8")


def update_web_default(model_name: str) -> None:
    config_path = Path("/home/pnt/drone_web/backend/config.py")
    if not config_path.exists():
        return
    text = config_path.read_text(encoding="utf-8")
    updated = text.replace(
        next(
            line for line in text.splitlines()
            if line.startswith("DEFAULT_MODEL_NAME: str = ")
        ),
        f'DEFAULT_MODEL_NAME: str = "{model_name}"',
        1,
    )
    config_path.write_text(updated, encoding="utf-8")


def last_validation_map(run_dir: Path) -> float:
    csv_path = run_dir / "results.csv"
    if not csv_path.exists():
        return float("-inf")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return float("-inf")
    values = []
    for row in rows:
        for key, value in row.items():
            if key and "mAP50-95" in key:
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    pass
    return max(values, default=float("-inf"))


def copy_export(source: str | Path, destination: Path) -> str:
    source_path = Path(str(source))
    if source_path.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
    elif source_path.is_dir():
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source_path, destination)
    else:
        raise FileNotFoundError(source_path)
    return str(destination)


def main() -> None:
    status = {"status": "waiting", "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    write_status(status)
    while True:
        if MANIFEST.exists():
            matrix = json.loads(MANIFEST.read_text(encoding="utf-8"))
            if matrix.get("status") == "completed":
                break
        time.sleep(60)

    status.update({"status": "evaluating", "runs": []})
    write_status(status)
    candidates = []
    for run in matrix.get("runs", []):
        run_dir = RUN_ROOT / run["name"]
        best = run_dir / "weights" / "best.pt"
        record = dict(run, best=str(best), val_map50_95=last_validation_map(run_dir))
        if not best.exists():
            record["postprocess_status"] = "missing_best"
        else:
            try:
                metrics = YOLO(str(best)).val(
                    data=str(DATA / "data.yaml"),
                    split="test",
                    imgsz=int(run["imgsz"]),
                    batch=8,
                    device=0,
                    workers=4,
                    project=str(DEPLOY_ROOT / "test_evaluations"),
                    name=run["name"],
                    plots=True,
                    verbose=False,
                )
                record.update(
                    {
                        "test_map50": float(metrics.box.map50),
                        "test_map50_95": float(metrics.box.map),
                        "test_precision": float(metrics.box.mp),
                        "test_recall": float(metrics.box.mr),
                        "postprocess_status": "evaluated",
                    }
                )
                candidates.append(record)
            except Exception as exc:  # keep other candidates available
                record.update({"postprocess_status": "evaluation_failed", "error": repr(exc)})
        status["runs"].append(record)
        write_status(status)

    if not candidates:
        raise RuntimeError("No completed run produced a test evaluation")
    selected = max(candidates, key=lambda item: item["val_map50_95"])
    status.update({"status": "exporting", "selected_by_validation": selected})
    write_status(status)

    best = Path(selected["best"])
    model = YOLO(str(best))
    base_name = f"fresh_{selected['model']}_img{int(selected['imgsz'])}_best"
    WEB_MODELS.mkdir(parents=True, exist_ok=True)
    exports = {"pt": str(best)}
    exports["web_pt"] = copy_export(best, WEB_MODELS / f"{base_name}.pt")
    for fmt, suffix in (("onnx", ".onnx"), ("ncnn", "_ncnn"), ("tflite", ".tflite")):
        try:
            result = model.export(format=fmt, imgsz=int(selected["imgsz"]), device=0, half=False, simplify=True)
            destination = DEPLOY_ROOT / f"{base_name}{suffix}"
            exports[fmt] = copy_export(result, destination)
            if fmt == "onnx":
                web_onnx = WEB_MODELS / f"{base_name}.onnx"
                exports["web_onnx"] = copy_export(result, web_onnx)
                update_web_default(web_onnx.name)
                exports["web_default_model"] = web_onnx.name
        except Exception as exc:
            exports[f"{fmt}_error"] = repr(exc)

    status.update({"status": "deployed", "exports": exports, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    write_status(status)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write_status({"status": "failed", "error": repr(exc), "traceback": traceback.format_exc()})
        raise
