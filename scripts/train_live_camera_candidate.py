#!/usr/bin/env python3
"""Fine-tune the frozen YOLOv8n checkpoint for the real USB-camera domain."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import torch
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEIGHTS = (
    ROOT
    / "artifacts/experiments/scope18-v3-labelrepair/scope18-yolov8n-480/attempt-batch16/weights/best.pt"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed/drone-live-camera-v1/data.yaml")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--project", type=Path, default=ROOT / "artifacts/experiments/live-camera-v1")
    parser.add_argument("--name", default="yolov8n-480-finetune")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--close-mosaic", type=int, default=10)
    parser.add_argument("--lr0", type=float, default=0.01)
    args = parser.parse_args()
    for path in (args.data, args.weights):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required")

    provenance = {
        "purpose": "USB-camera domain adaptation",
        "base_weights": str(args.weights.resolve()),
        "base_weights_sha256": sha256(args.weights),
        "data": str(args.data.resolve()),
        "data_sha256": sha256(args.data),
        "epochs": args.epochs,
        "batch": args.batch,
        "imgsz": 480,
        "seed": 42,
        "channel_dropout": 0.0,
        "close_mosaic": args.close_mosaic,
        "lr0": args.lr0,
        "v3_test_accessed": False,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "started_at_unix": time.time(),
    }
    print(json.dumps(provenance, indent=2), flush=True)
    model = YOLO(str(args.weights.resolve()))
    result = model.train(
        data=str(args.data.resolve()),
        epochs=args.epochs,
        imgsz=480,
        batch=args.batch,
        workers=args.workers,
        device=0,
        seed=42,
        deterministic=True,
        amp=True,
        cache=False,
        patience=12,
        pretrained=True,
        project=str(args.project.resolve()),
        name=args.name,
        exist_ok=False,
        plots=True,
        verbose=True,
        close_mosaic=args.close_mosaic,
        lr0=args.lr0,
    )
    provenance["finished_at_unix"] = time.time()
    save_dir = Path(model.trainer.save_dir)
    provenance["save_dir"] = str(save_dir)
    provenance["best_pt"] = str(save_dir / "weights/best.pt")
    provenance["best_pt_sha256"] = sha256(save_dir / "weights/best.pt")
    (save_dir / "live_camera_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(provenance, indent=2), flush=True)


if __name__ == "__main__":
    main()
