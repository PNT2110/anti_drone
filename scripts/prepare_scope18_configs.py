"""Prepare immutable Scope 18 run configurations; does not train."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
CONFIG_DIR = ROOT / "configs/training/scope18"
OUTPUT_ROOT = ROOT / "artifacts/experiments/scope18-v3-labelrepair"
WEIGHTS = {
    "yolov8n": (Path("/home/pnt/Desktop/antidrone/model/yolov8n.pt"), "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36"),
    "yolov11n": (Path("/home/pnt/Desktop/antidrone/model/yolo11n.pt"), "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"),
    "yolo26n": (Path("/home/pnt/Desktop/antidrone/model/yolo26n.pt"), "9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if OUTPUT_ROOT.exists():
        raise RuntimeError(f"BLOCKED: Scope 18 output root already exists; refusing overwrite: {OUTPUT_ROOT}")
    manifest_hash = sha256(DATASET / "manifest.json")
    registry_hash = sha256(DATASET / "split_registry.json")
    data_hash = sha256(DATASET / "data.yaml")
    repair_audit_hash = sha256(ROOT / ".runtime/scope17/label_repair_audit.json")
    configs = []
    for model_id, (weight, weight_hash) in WEIGHTS.items():
        if not weight.is_file() or sha256(weight) != weight_hash:
            raise RuntimeError(f"BLOCKED: starting weight checksum mismatch: {model_id}")
        for imgsz in (640, 480):
            run_id = f"scope18-{model_id}-{imgsz}"
            path = CONFIG_DIR / f"{run_id}.json"
            config = {
                "run_id": run_id,
                "status": "PREPARED_NOT_STARTED",
                "data": str(DATASET / "data.yaml"),
                "dataset_manifest_sha256": manifest_hash,
                "dataset_split_registry_sha256": registry_hash,
                "repair_audit_sha256": repair_audit_hash,
                "source_mapping_reference": ".runtime/scope13/rgbt_archive_mapping.csv",
                "seed": 42,
                "epochs": 100,
                "imgsz": imgsz,
                "batch_start": 16,
                "batch_fallback_policy": [16, 8, 4],
                "workers": 4,
                "device": "0",
                "model_id": model_id,
                "starting_weight_path": str(weight),
                "starting_weight_sha256": weight_hash,
                "optimizer": "auto (Ultralytics default)",
                "patience": 1000,
                "amp": True,
                "deterministic": True,
                "cache": False,
                "augmentation": "Ultralytics default train augmentations as invoked by existing scripts/train_gpu.py",
                "channel_dropout": {"probability": 0.10, "type": "training-only Dropout2d feature-map hook; Detect head untouched"},
                "validation_policy": "V3 val only; no V3 test read for selection",
                "test_policy": "locked; final test belongs to a later frozen-evaluation scope",
                "resume_policy": "only last.pt from this exact run_id/model/imgsz/dataset/seed/batch",
                "output_root": str(OUTPUT_ROOT),
                "run_directory": str(OUTPUT_ROOT / run_id),
                "training_not_run": True,
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
            configs.append(str(path))
    result = {"status": "PASS", "dataset_manifest_sha256": manifest_hash, "dataset_split_registry_sha256": registry_hash, "repair_audit_sha256": repair_audit_hash, "configs": configs, "training_started": False}
    runtime = ROOT / ".runtime/scope18"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "config_preparation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
