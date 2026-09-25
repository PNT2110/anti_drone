"""Read a few batches with the installed Ultralytics loader, without training."""

from __future__ import annotations

import json
import platform
from pathlib import Path

from ultralytics import YOLO
from ultralytics.data import YOLODataset


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v2-executable"
OUT = ROOT / ".runtime/scope12/loader_smoke.json"
WEIGHTS = {
    "yolov8n": Path("/home/pnt/Desktop/antidrone/model/yolov8n.pt"),
    "yolov11n": Path("/home/pnt/Desktop/antidrone/model/yolo11n.pt"),
    "yolo26n": Path("/home/pnt/Desktop/antidrone/model/yolo26n.pt"),
}


def main() -> int:
    result = {"status": "PASS", "python": platform.python_version(), "ultralytics": None, "models": {}, "splits": {}}
    import ultralytics

    result["ultralytics"] = ultralytics.__version__
    for model_id, weight in WEIGHTS.items():
        model = YOLO(str(weight))
        result["models"][model_id] = {"weight": str(weight), "task": model.task, "loaded": True}
    for split in ("train", "val", "test"):
        dataset = YOLODataset(
            img_path=str(DATASET / "images" / split),
            imgsz=640,
            batch_size=2,
            augment=False,
            data={"names": {0: "drone"}, "nc": 1},
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
