#!/usr/bin/env python3
"""Train the Phase 2 YOLO baselines on the CUDA GPU.

The run is deliberately configured with patience larger than epochs so early
stopping cannot end a requested run before all epochs have completed. Channel
dropout is installed as a training-only forward hook on feature maps: each
sample gets an independent channel mask, reducing co-adaptation without
changing the exported inference graph.
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLO


WEIGHTS = {
    "yolov8n": Path("/home/pnt/Desktop/antidrone/model/yolov8n.pt"),
    "yolov11n": Path("/home/pnt/Desktop/antidrone/model/yolo11n.pt"),
    "yolo26n": Path("/home/pnt/Desktop/antidrone/model/yolo26n.pt"),
}


def git_state() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "not-a-git-worktree"


def install_channel_dropout(model: YOLO, probability: float):
    if probability <= 0:
        return []
    feature_indices = [i for i, layer in enumerate(model.model.model) if i < len(model.model.model) - 1]
    # Use late backbone/neck feature maps and leave the Detect head untouched.
    selected = feature_indices[-8:-2]
    dropouts = []
    handles = []

    def hook_factory():
        dropout = torch.nn.Dropout2d(p=probability)
        dropouts.append(dropout)

        def hook(_module, _inputs, output):
            if _module.training and isinstance(output, torch.Tensor) and output.ndim == 4:
                return dropout(output)
            return output

        return hook

    for index in selected:
        handles.append(model.model.model[index].register_forward_hook(hook_factory()))
    print(f"channel_dropout_p={probability} feature_layers={selected}", flush=True)
    return handles


def train_one(args: argparse.Namespace, model_id: str) -> None:
    weight = WEIGHTS[model_id]
    if not weight.exists():
        raise FileNotFoundError(weight)
    run_name = f"baseline-640-s{args.seed}-drop{str(args.dropout).replace('.', '')}"
    project = args.output_root / "drone-single-class" / model_id
    project.mkdir(parents=True, exist_ok=True)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    resume_checkpoint = args.resume_checkpoint.resolve() if args.resume_checkpoint else None
    model_source = resume_checkpoint if resume_checkpoint else weight
    model = YOLO(str(model_source))
    handles = install_channel_dropout(model, args.dropout)
    started = time.time()
    provenance = {
        "model_id": model_id,
        "weights": str(model_source),
        "data": str(args.data.resolve()),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "seed": args.seed,
        "device": args.device,
        "batch": args.batch,
        "workers": args.workers,
        "amp": True,
        "patience": max(args.epochs + 1, 1000),
        "channel_dropout": args.dropout,
        "dropout_type": "per-sample Dropout2d feature-map channel mask",
        "resume_checkpoint": str(resume_checkpoint) if resume_checkpoint else None,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "git": git_state(),
        "started_at_unix": started,
    }
    print(json.dumps(provenance, indent=2), flush=True)

    try:
        train_kwargs = dict(
            data=str(args.data.resolve()),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            workers=args.workers,
            device=args.device,
            seed=args.seed,
            deterministic=True,
            amp=True,
            cache=False,
            patience=max(args.epochs + 1, 1000),
            pretrained=True,
            project=str(project.resolve()),
            name=run_name,
            exist_ok=False,
            plots=True,
            verbose=True,
        )
        if resume_checkpoint:
            # Ultralytics restores optimizer/scaler/epoch from last.pt and uses
            # the checkpoint's existing run directory when resume=True.
            train_kwargs["resume"] = True
        model.train(**train_kwargs)
    finally:
        for handle in handles:
            handle.remove()
        provenance["finished_at_unix"] = time.time()
        run_dir = Path(getattr(getattr(model, "trainer", None), "save_dir", project.resolve() / run_name))
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "anti_drone_provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/processed/drone-single-class/data.yaml"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/experiments"))
    parser.add_argument("--models", nargs="+", choices=sorted(WEIGHTS), default=["yolov8n", "yolov11n", "yolo26n"])
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--device", default="0")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dropout", type=float, default=0.10)
    parser.add_argument(
        "--resume-checkpoint",
        type=Path,
        default=None,
        help="Resume one model from a YOLO last.pt checkpoint; use with a single --models entry.",
    )
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for Phase 2 training")
    if not args.data.exists():
        raise FileNotFoundError(args.data)
    if args.resume_checkpoint:
        if len(args.models) != 1:
            raise ValueError("--resume-checkpoint requires exactly one model in --models")
        if not args.resume_checkpoint.exists():
            raise FileNotFoundError(args.resume_checkpoint)
    for model_id in args.models:
        print(f"===== START {model_id} =====", flush=True)
        train_one(args, model_id)
        print(f"===== DONE {model_id} =====", flush=True)


if __name__ == "__main__":
    main()
