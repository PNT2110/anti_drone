"""Load all V3 candidate splits and the six approved pretrained weights."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

from ultralytics import YOLO
from ultralytics.data import YOLODataset


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v3-candidate"
OUT = ROOT / ".runtime/scope15/loader_smoke.json"
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
    import ultralytics
    import torch
    import yaml

    yaml_text = (DATASET / "data.yaml").read_text(encoding="utf-8")
    data_config = yaml.safe_load(yaml_text)
    if data_config != {
        "path": str(DATASET),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {0: "drone"},
    }:
        raise RuntimeError("BLOCKED: candidate data.yaml does not describe the expected dataset")
    result = {
        "status": "PASS",
        "python": platform.python_version(),
        "ultralytics": ultralytics.__version__,
        "torch": torch.__version__,
        "cuda": torch.cuda.is_available(),
        "data_yaml_parsed": True,
        "models": {},
        "splits": {},
        "training_run": False,
    }
    for model_id, weight in WEIGHTS.items():
        model = YOLO(str(weight))
        result["models"][model_id] = {
            "weight": str(weight),
            "weight_sha256": sha256(weight),
            "task": model.task,
            "loaded": True,
        }
    for split in ("train", "val", "test"):
        dataset = YOLODataset(
            img_path=str(DATASET / "images" / split),
            imgsz=640,
            batch_size=2,
            augment=False,
            data={"names": data_config["names"], "nc": 1},
            task="detect",
        )
        sample = dataset[0]
        result["splits"][split] = {
            "length": len(dataset),
            "sample_image": sample["im_file"],
            "tensor_shape": list(sample["img"].shape),
            "class_tensor_shape": list(sample["cls"].shape),
            "bbox_tensor_shape": list(sample["bboxes"].shape),
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
