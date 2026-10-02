"""Fresh YOLO training matrix for the FPV indoor/outdoor drone dataset.

This script intentionally starts new runs and never resumes an old checkpoint.
It is mirrored on the training server at /mnt/home_big/pnt/train_matrix_fresh.py.
"""

from pathlib import Path
import json
import os
import time
import traceback

from ultralytics import YOLO


DATA = Path(os.environ.get("FPV_DATA", "/mnt/home_big/pnt/anti_drone_data/data_train"))
RUN_ROOT = Path(
    os.environ.get(
        "FPV_RUN_ROOT",
        "/mnt/home_big/pnt/anti_drone_data/training_runs/fresh_matrix",
    )
)
EPOCHS = int(os.environ.get("FPV_EPOCHS", "30"))
BATCH = int(os.environ.get("FPV_BATCH", "8"))
WORKERS = int(os.environ.get("FPV_WORKERS", "4"))
MODELS = [("yolov8", "yolov8n.pt"), ("yolo11", "yolo11n.pt"), ("yolo26", "yolo26n.pt")]
SIZES = [480, 640]


def main() -> None:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    manifest_path = RUN_ROOT / "matrix_manifest.json"
    manifest = {
        "status": "running",
        "epochs": EPOCHS,
        "batch": BATCH,
        "models": [model_id for model_id, _ in MODELS],
        "sizes": SIZES,
        "runs": [],
    }

    def save_manifest() -> None:
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if not (DATA / "data.yaml").exists():
        raise FileNotFoundError(DATA / "data.yaml")

    save_manifest()
    for model_id, base_weights in MODELS:
        for imgsz in SIZES:
            run_name = f"{model_id}_img{imgsz}"
            record = {
                "name": run_name,
                "model": model_id,
                "base_weights": base_weights,
                "imgsz": imgsz,
                "status": "running",
                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
            manifest["runs"].append(record)
            save_manifest()
            print(f"START {run_name}", flush=True)
            try:
                model = YOLO(base_weights)
                model.train(
                    data=str(DATA / "data.yaml"),
                    project=str(RUN_ROOT),
                    name=run_name,
                    exist_ok=False,
                    epochs=EPOCHS,
                    imgsz=imgsz,
                    batch=BATCH,
                    device=0,
                    workers=WORKERS,
                    pretrained=True,
                    seed=42,
                    deterministic=True,
                    amp=True,
                    cache=False,
                    patience=8,
                    weight_decay=0.0005,
                    label_smoothing=0.05,
                    mosaic=1.0,
                    mixup=0.10,
                    degrees=5.0,
                    translate=0.10,
                    scale=0.50,
                    fliplr=0.50,
                    hsv_h=0.015,
                    hsv_s=0.70,
                    hsv_v=0.40,
                    close_mosaic=10,
                    cos_lr=True,
                    save_period=5,
                    plots=True,
                    val=True,
                    verbose=True,
                )
                best = RUN_ROOT / run_name / "weights" / "best.pt"
                record.update(
                    {
                        "status": "completed" if best.exists() else "completed_without_best",
                        "best": str(best),
                        "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    }
                )
                print(f"DONE {run_name} best={best.exists()}", flush=True)
            except Exception as exc:  # keep the matrix moving if one run fails
                record.update(
                    {
                        "status": "failed",
                        "error": repr(exc),
                        "traceback": traceback.format_exc(),
                        "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    }
                )
                print(f"FAILED {run_name}: {exc!r}", flush=True)
            save_manifest()

    manifest["status"] = "completed"
    manifest["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    save_manifest()
    print("MATRIX_COMPLETED", flush=True)


if __name__ == "__main__":
    main()
