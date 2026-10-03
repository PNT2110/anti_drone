"""Compare fresh drone models at confidence 0.1..1.0 on reviewed video frames.

Boxes in the CSV are manually reviewed diagnostics. They are a small sample,
not a source-disjoint test set or a full-video identity ground truth.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import cv2


CONFIDENCES = tuple(step / 10 for step in range(1, 11))
IOU_THRESHOLDS = (0.30, 0.50)
CLIPS = ("short", "indoor", "outdoor")
MODEL_NAMES = (
    "drone-yolov8n-fresh-480.pt",
    "drone-yolov8n-fresh-640.pt",
    "drone-yolo11n-fresh-480.pt",
    "drone-yolo11n-fresh-640.pt",
    "drone-yolo26n-fresh-480.pt",
    "drone-yolo26n-fresh-640.pt",
)


def intersection_over_union(first: list[float], second: list[float]) -> float:
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def match_count(predictions: list[dict], truths: list[dict], threshold: float) -> int:
    pairs = sorted(
        ((intersection_over_union(prediction["box"], truth["box"]), pi, ti)
         for pi, prediction in enumerate(predictions)
         for ti, truth in enumerate(truths)),
        reverse=True,
    )
    used_predictions: set[int] = set()
    used_truths: set[int] = set()
    matches = 0
    for overlap, pi, ti in pairs:
        if overlap < threshold:
            break
        if pi not in used_predictions and ti not in used_truths:
            used_predictions.add(pi)
            used_truths.add(ti)
            matches += 1
    return matches


def load_review(images_dir: Path, labels_csv: Path):
    frames = []
    keys = set()
    for clip in CLIPS:
        paths = sorted((images_dir / clip).glob("*.jpg"))
        if not paths:
            raise SystemExit(f"No review images in {images_dir / clip}")
        for index, path in enumerate(paths):
            frame = cv2.imread(str(path))
            if frame is None:
                raise SystemExit(f"Cannot read {path}")
            frames.append({"clip": clip, "index": index, "path": path, "frame": frame, "truth": []})
            keys.add((clip, index))

    lookup = {(item["clip"], item["index"]): item for item in frames}
    with labels_csv.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            key = (row["clip"], int(row["image_index"]))
            if key not in keys:
                raise SystemExit(f"Label has no image: {key}")
            box = [float(row[name]) for name in ("x1", "y1", "x2", "y2")]
            height, width = lookup[key]["frame"].shape[:2]
            if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
                raise SystemExit(f"Invalid box {key}: {box} for {width}x{height}")
            lookup[key]["truth"].append({"object": row["object"], "box": box})
    return frames


def draw_preview(frames: list[dict], output_dir: Path) -> None:
    for item in frames:
        output = output_dir / "reviewed" / item["clip"] / item["path"].name
        output.parent.mkdir(parents=True, exist_ok=True)
        annotated = item["frame"].copy()
        for truth in item["truth"]:
            x1, y1, x2, y2 = map(round, truth["box"])
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated, truth["object"], (x1, max(18, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2, cv2.LINE_AA)
        if not cv2.imwrite(str(output), annotated):
            raise SystemExit(f"Cannot write {output}")
    print(f"previewed {len(frames)} frames with {sum(len(item['truth']) for item in frames)} boxes")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args()

    frames = load_review(args.images, args.labels)
    if args.preview_only:
        draw_preview(frames, args.output)
        return 0
    if args.models_dir is None:
        parser.error("--models-dir is required unless --preview-only is set")

    from ultralytics import YOLO

    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    predictions_archive = []
    for model_name in MODEL_NAMES:
        model_path = args.models_dir / model_name
        if not model_path.is_file():
            raise SystemExit(f"Missing model {model_path}")
        model = YOLO(str(model_path), task="detect")
        counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
        for item in frames:
            output = model.predict(item["frame"], imgsz=args.imgsz, conf=0.10,
                                   iou=0.45, verbose=False)[0]
            boxes = output.boxes.xyxy.cpu().numpy().tolist() if output.boxes is not None else []
            confidences = output.boxes.conf.cpu().numpy().tolist() if output.boxes is not None else []
            raw = [{"box": [round(float(x), 2) for x in box], "confidence": round(float(score), 5)}
                   for box, score in zip(boxes, confidences)]
            predictions_archive.append({
                "model": model_name, "clip": item["clip"], "image_index": item["index"],
                "image": item["path"].name, "predictions": raw,
            })
            for confidence in CONFIDENCES:
                selected = [prediction for prediction in raw if prediction["confidence"] >= confidence]
                for iou_threshold in IOU_THRESHOLDS:
                    tp = match_count(selected, item["truth"], iou_threshold)
                    values = counts[(item["clip"], confidence, iou_threshold)]
                    values["tp"] += tp
                    values["fp"] += len(selected) - tp
                    values["fn"] += len(item["truth"]) - tp
        del model
        for (clip, confidence, iou_threshold), values in counts.items():
            tp, fp, fn = values["tp"], values["fp"], values["fn"]
            precision = tp / max(1, tp + fp)
            recall = tp / max(1, tp + fn)
            f1 = 2 * precision * recall / max(1e-12, precision + recall)
            results.append({
                "model": model_name, "clip": clip, "confidence": confidence,
                "iou": iou_threshold, "tp": tp, "fp": fp, "fn": fn,
                "precision": round(precision, 5), "recall": round(recall, 5),
                "f1": round(f1, 5),
            })
        print(f"finished {model_name} ({len(frames)} reviewed frames)", flush=True)

    (args.output / "sample_matrix.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (args.output / "sample_predictions.json").write_text(
        json.dumps(predictions_archive, indent=2), encoding="utf-8"
    )
    with (args.output / "sample_matrix.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print(f"saved {args.output / 'sample_matrix.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
