"""Load the repaired candidate with the project Ultralytics environment."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import yaml
from ultralytics import YOLO
from ultralytics.data import YOLODataset


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
OUT = ROOT / ".runtime/scope17/loader_smoke.json"
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
    import torch
    import ultralytics

    config = yaml.safe_load((DATASET / "data.yaml").read_text(encoding="utf-8"))
    if config != {"path": str(DATASET), "train": "images/train", "val": "images/val", "test": "images/test", "names": {0: "drone"}}:
        raise RuntimeError("BLOCKED: repaired candidate data.yaml mismatch")
    result = {"status": "PASS", "training_run": False, "python": platform.python_version(), "torch": torch.__version__, "ultralytics": ultralytics.__version__, "cuda": torch.cuda.is_available(), "data_yaml_parsed": True, "models": {}, "splits": {}}
    for model_id, weight in WEIGHTS.items():
        model = YOLO(str(weight))
        result["models"][model_id] = {"loaded": True, "task": model.task, "weight": str(weight), "weight_sha256": sha256(weight)}
    for split in ("train", "val", "test"):
        dataset = YOLODataset(img_path=str(DATASET / "images" / split), imgsz=640, batch_size=2, augment=False, data={"names": {0: "drone"}, "nc": 1}, task="detect")
        sample = dataset[0]
        result["splits"][split] = {"length": len(dataset), "sample_image": sample["im_file"], "tensor_shape": list(sample["img"].shape), "class_tensor_shape": list(sample["cls"].shape), "bbox_tensor_shape": list(sample["bboxes"].shape)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
