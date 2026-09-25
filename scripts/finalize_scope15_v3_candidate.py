"""Finalize the audited Scope 15 candidate for loader use, without training."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v3-candidate"
AUDIT = ROOT / ".runtime/scope15/direct_disk_audit.json"
CONFIG_DIR = ROOT / "configs/training/scope15"
RUNTIME = ROOT / ".runtime/scope15/finalization.json"
EXPECTED_WEIGHTS = {
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


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if not DATASET.is_dir() or not (DATASET / "manifest.json").is_file():
        raise RuntimeError("BLOCKED: candidate dataset/manifest missing")
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS":
        raise RuntimeError("BLOCKED: direct disk audit is not PASS")
    if (DATASET / "data.yaml").exists():
        raise RuntimeError("BLOCKED: refusing to overwrite existing data.yaml")
    for model_id, (weight, expected_hash) in EXPECTED_WEIGHTS.items():
        if not weight.is_file() or sha256(weight) != expected_hash:
            raise RuntimeError(f"BLOCKED: pretrained weight checksum mismatch: {model_id}")

    manifest_hash = sha256(DATASET / "manifest.json")
    registry_hash = sha256(DATASET / "split_registry.json")
    data_yaml = """path: /run/media/pnt/APP/anti_drone/data/processed/drone-single-class-v3-candidate
train: images/train
val: images/val
test: images/test
names:
  0: drone
"""
    (DATASET / "data.yaml").write_text(data_yaml, encoding="utf-8")
    configs = []
    for model_id, (weight, weight_hash) in EXPECTED_WEIGHTS.items():
        for imgsz in (480, 640):
            output_root = ROOT / f"artifacts/experiments/scope15-v3/imgsz-{imgsz}-s42"
            config = {
                "amp": True,
                "batch": 16,
                "candidate_status": "HOLDOUT_PRESERVING_V3_CANDIDATE",
                "data": str(DATASET / "data.yaml"),
                "dataset_manifest_sha256": manifest_hash,
                "dataset_split_registry_sha256": registry_hash,
                "device": "0",
                "epochs": 100,
                "expected_project": str(output_root / "drone-single-class" / model_id),
                "excluded_quarantine": {"groups": 4172, "samples": 6505},
                "imgsz": imgsz,
                "model_id": model_id,
                "output_root": str(output_root),
                "pretrained": True,
                "resume_policy": "resume only from this configuration's own last.pt; never cross-model/cross-size resume",
                "seed": 42,
                "session_disjoint": "UNVERIFIED",
                "status": "PREPARED_NOT_TRAINED",
                "test_policy": "V3 test is locked; validation only for checkpoint/parameter selection",
                "training_command_template": f"python scripts/train_gpu.py --data {DATASET / 'data.yaml'} --models {model_id} --imgsz {imgsz} --seed 42 --batch 16 --device 0 --output-root {output_root}",
                "training_not_run": True,
                "weight_path": str(weight),
                "weight_sha256": weight_hash,
                "workers": 4,
            }
            path = CONFIG_DIR / f"{model_id}_{imgsz}.json"
            write_json(path, config)
            configs.append(str(path))
    result = {
        "status": "PASS",
        "data_yaml": str(DATASET / "data.yaml"),
        "direct_disk_audit_sha256": sha256(AUDIT),
        "dataset_manifest_sha256": manifest_hash,
        "dataset_split_registry_sha256": registry_hash,
        "configs": configs,
        "training_run": False,
        "production_status": "CANDIDATE_ONLY",
    }
    write_json(RUNTIME, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
