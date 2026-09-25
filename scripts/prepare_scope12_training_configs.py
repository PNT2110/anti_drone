"""Prepare six non-training Scope 12 run configurations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v2-executable"
CONFIG_DIR = ROOT / "configs/training/scope12"
WEIGHTS = {
    "yolov8n": Path("/home/pnt/Desktop/antidrone/model/yolov8n.pt"),
    "yolov11n": Path("/home/pnt/Desktop/antidrone/model/yolo11n.pt"),
    "yolo26n": Path("/home/pnt/Desktop/antidrone/model/yolo26n.pt"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    provenance = json.loads((DATASET / "training_provenance.json").read_text(encoding="utf-8"))
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    generated = []
    for model_id, weights in WEIGHTS.items():
        if not weights.is_file():
            raise RuntimeError(f"BLOCKED: missing exact repository weight: {weights}")
        for imgsz in (640, 480):
            config = {
                "status": "PREPARED_NOT_TRAINED",
                "model_id": model_id,
                "weight_path": str(weights),
                "weight_sha256": sha256(weights),
                "data": str((DATASET / "data.yaml").resolve()),
                "dataset_manifest_sha256": provenance["dataset_manifest_sha256"],
                "split_registry_sha256": provenance["split_registry_sha256"],
                "seed": 42,
                "imgsz": imgsz,
                "batch": 16,
                "device": "0",
                "workers": 4,
                "epochs": 100,
                "amp": True,
                "pretrained": True,
                "output_root": str((ROOT / "artifacts/experiments/scope12-v2" / f"imgsz-{imgsz}-s42").resolve()),
                "expected_project": str((ROOT / "artifacts/experiments/scope12-v2" / f"imgsz-{imgsz}-s42" / "drone-single-class" / model_id).resolve()),
                "resume_policy": "resume only from this configuration's own last.pt; never cross-model/cross-size resume",
                "test_policy": "test is held out; validation only for checkpoint/parameter selection",
                "excluded_quarantine": {"samples": 6505, "groups": 4172},
                "training_command_template": f"python scripts/train_gpu.py --data {DATASET / 'data.yaml'} --models {model_id} --imgsz {imgsz} --seed 42 --batch 16 --device 0 --output-root artifacts/experiments/scope12-v2/imgsz-{imgsz}-s42",
                "training_not_run": True,
            }
            path = CONFIG_DIR / f"{model_id}_{imgsz}.json"
            path.write_text(json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
            generated.append(str(path.relative_to(ROOT)))
    print(json.dumps({"configs": generated}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
