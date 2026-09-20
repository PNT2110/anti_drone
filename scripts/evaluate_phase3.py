#!/usr/bin/env python3
"""Run the Phase 3 validation/test protocol and select one release candidate.

The dataset currently contains extracted image frames, not standalone negative
video files.  Negative-frame evaluation is therefore reported explicitly as a
30 FPS proxy in ``negative_video_metrics.csv``; it is not presented as a real
camera-video measurement.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
from ultralytics import YOLO


MODEL_RUNS = {
    "yolov8n": Path("artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2"),
    "yolov11n": Path("artifacts/experiments/drone-single-class/yolov11n/baseline-640-s42-drop01"),
    "yolo26n": Path("artifacts/experiments/drone-single-class/yolo26n/baseline-640-s42-drop01"),
}
SIZE_BINS = ("<4", "4-8", "8-16", "16-32", "32-64", ">64")
IOU_THRESHOLDS = tuple(np.arange(0.50, 0.951, 0.05))


@dataclass
class Record:
    image: Path
    # Compact float32 array with columns [confidence, x1, y1, x2, y2].
    predictions: np.ndarray
    ground_truth: list[np.ndarray]
    image_size: tuple[int, int]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "not-a-git-worktree"


def load_ground_truth(label_path: Path, width: int, height: int) -> list[np.ndarray]:
    boxes: list[np.ndarray] = []
    if not label_path.exists():
        return boxes
    for line in label_path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 5:
            continue
        class_id, xc, yc, bw, bh = map(float, fields)
        if int(class_id) != 0:
            continue
        x1 = (xc - bw / 2) * width
        y1 = (yc - bh / 2) * height
        x2 = (xc + bw / 2) * width
        y2 = (yc + bh / 2) * height
        boxes.append(np.array([x1, y1, x2, y2], dtype=np.float32))
    return boxes


def box_iou(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, float(a[2] - a[0])) * max(0.0, float(a[3] - a[1]))
    area_b = max(0.0, float(b[2] - b[0])) * max(0.0, float(b[3] - b[1]))
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def size_bin(box: np.ndarray) -> str:
    size = max(float(box[2] - box[0]), float(box[3] - box[1]))
    if size < 4:
        return "<4"
    if size < 8:
        return "4-8"
    if size < 16:
        return "8-16"
    if size < 32:
        return "16-32"
    if size < 64:
        return "32-64"
    return ">64"


def match_image(
    predictions: np.ndarray,
    ground_truth: list[np.ndarray],
    match_iou: float,
) -> tuple[int, int, int, set[int]]:
    matched_gt: set[int] = set()
    true_positive = 0
    false_positive = 0
    if predictions.size == 0:
        predictions = np.empty((0, 5), dtype=np.float32)
    ordered = predictions[np.argsort(predictions[:, 0])[::-1]]
    for row in ordered:
        prediction = row[1:5]
        candidates = [
            (box_iou(prediction, target), index)
            for index, target in enumerate(ground_truth)
            if index not in matched_gt
        ]
        if candidates:
            best_iou, best_index = max(candidates)
        else:
            best_iou, best_index = 0.0, -1
        if best_iou >= match_iou:
            matched_gt.add(best_index)
            true_positive += 1
        else:
            false_positive += 1
    false_negative = len(ground_truth) - len(matched_gt)
    return true_positive, false_positive, false_negative, matched_gt


def summary(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def collect_predictions(
    checkpoint: Path,
    image_paths: list[Path],
    label_root: Path,
    imgsz: int,
    batch: int,
    device: str,
    nms_iou: float,
    prediction_conf: float,
    cache_path: Path,
) -> int:
    """Run inference and write one compact JSON record per image.

    Keeping all validation predictions in a Python list caused the full Phase 3
    run to reach the machine's RAM limit.  The cache is deliberately line
    oriented so metrics can make multiple streaming passes without retaining
    thousands of images in memory.
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(checkpoint))
    count = 0
    with cache_path.open("w", encoding="utf-8") as cache:
        # Ultralytics can materialize a large list passed as ``source`` before
        # yielding the first result.  Chunking is therefore required even
        # though the results themselves are streamed to disk.
        chunk_size = max(batch * 4, 4)
        for start in range(0, len(image_paths), chunk_size):
            chunk = image_paths[start : start + chunk_size]
            stream = model.predict(
                source=[str(path) for path in chunk],
                imgsz=imgsz,
                batch=batch,
                device=device,
                # Keep every useful candidate down to the requested floor. The
                # predictions are written immediately, so this can be lower
                # than the threshold sweep without exhausting host RAM.
                conf=prediction_conf,
                iou=nms_iou,
                max_det=100,
                stream=True,
                verbose=False,
            )
            for result in stream:
                result_path = Path(result.path)
                height, width = result.orig_shape
                boxes = result.boxes
                xyxy = boxes.xyxy.cpu().numpy() if boxes is not None else np.empty((0, 4))
                confidence = boxes.conf.cpu().numpy() if boxes is not None else np.empty((0,))
                predictions = np.column_stack((confidence, xyxy)).astype(np.float32, copy=False)
                label_path = label_root / f"{result_path.stem}.txt"
                ground_truth = load_ground_truth(label_path, width, height)
                cache.write(
                    json.dumps(
                        {
                            "image": result_path.name,
                            "predictions": predictions.tolist(),
                            "ground_truth": [box.tolist() for box in ground_truth],
                            "image_size": [int(width), int(height)],
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                count += 1
            del stream
            cache.flush()
            gc.collect()
    del model
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass
    if count != len(image_paths):
        raise RuntimeError(f"Prediction count mismatch: expected {len(image_paths)}, got {count}")
    return count


def iter_cached_records(cache_path: Path) -> Iterator[Record]:
    with cache_path.open(encoding="utf-8") as cache:
        for line in cache:
            item = json.loads(line)
            yield Record(
                image=Path(item["image"]),
                predictions=np.asarray(item["predictions"], dtype=np.float32).reshape(-1, 5),
                ground_truth=[np.asarray(box, dtype=np.float32) for box in item["ground_truth"]],
                image_size=(int(item["image_size"][0]), int(item["image_size"][1])),
            )


def threshold_metrics(records: Iterator[Record], confidence: float, match_iou: float) -> dict:
    tp = fp = fn = 0
    for record in records:
        selected = record.predictions[record.predictions[:, 0] >= confidence]
        image_tp, image_fp, image_fn, _ = match_image(selected, record.ground_truth, match_iou)
        tp += image_tp
        fp += image_fp
        fn += image_fn
    return summary(tp, fp, fn) | {"confidence": confidence, "match_iou": match_iou}


def average_precision(cache_path: Path, iou_threshold: float) -> float:
    total_ground_truth = 0
    candidates: list[tuple[float, int, np.ndarray]] = []
    ground_truth_by_image: dict[int, list[np.ndarray]] = {}
    for image_index, record in enumerate(iter_cached_records(cache_path)):
        ground_truth_by_image[image_index] = record.ground_truth
        total_ground_truth += len(record.ground_truth)
        for row in record.predictions:
            candidates.append((float(row[0]), image_index, row[1:5].copy()))
    if total_ground_truth == 0:
        return 0.0
    candidates.sort(key=lambda item: item[0], reverse=True)
    matched_by_image: dict[int, set[int]] = {}
    true_positive = []
    false_positive = []
    for confidence, image_index, prediction in candidates:
        ground_truth = ground_truth_by_image[image_index]
        used = matched_by_image.setdefault(image_index, set())
        options = [
            (box_iou(prediction, target), gt_index)
            for gt_index, target in enumerate(ground_truth)
            if gt_index not in used
        ]
        best_iou, best_index = max(options) if options else (0.0, -1)
        if best_iou >= iou_threshold:
            used.add(best_index)
            true_positive.append(1)
            false_positive.append(0)
        else:
            true_positive.append(0)
            false_positive.append(1)
    tp = np.cumsum(true_positive)
    fp = np.cumsum(false_positive)
    recall = tp / total_ground_truth
    precision = tp / np.maximum(tp + fp, 1)
    levels = np.linspace(0, 1, 101)
    return float(np.mean([np.max(precision[recall >= level]) if np.any(recall >= level) else 0.0 for level in levels]))


def map_metrics(cache_path: Path) -> dict[str, float]:
    aps = [average_precision(cache_path, threshold) for threshold in IOU_THRESHOLDS]
    return {"mAP50": aps[0], "mAP50-95": float(np.mean(aps)), "AP_by_iou": dict(zip([f"{x:.2f}" for x in IOU_THRESHOLDS], aps))}


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def evaluate_size_bins(records: Iterator[Record], confidence: float, match_iou: float) -> list[dict]:
    counts = {label: {"gt": 0, "tp": 0, "fn": 0} for label in SIZE_BINS}
    for record in records:
        selected = record.predictions[record.predictions[:, 0] >= confidence]
        _, _, _, matched = match_image(selected, record.ground_truth, match_iou)
        for index, gt in enumerate(record.ground_truth):
            label = size_bin(gt)
            counts[label]["gt"] += 1
            if index in matched:
                counts[label]["tp"] += 1
            else:
                counts[label]["fn"] += 1
    rows = []
    for label in SIZE_BINS:
        item = counts[label]
        rows.append(
            {
                "size_bin_pixels": label,
                "gt": item["gt"],
                "tp": item["tp"],
                "fn": item["fn"],
                "recall": item["tp"] / item["gt"] if item["gt"] else 0.0,
                "confidence": confidence,
                "match_iou": match_iou,
                "size_definition": "max(bbox_width,bbox_height)",
            }
        )
    return rows


def negative_proxy_from_cache(cache_path: Path, confidence: float, fps: float = 30.0) -> dict:
    negative_frames = 0
    false_alarm_frames = 0
    for record in iter_cached_records(cache_path):
        if not record.ground_truth:
            negative_frames += 1
            false_alarm_frames += int(np.any(record.predictions[:, 0] >= confidence))
    duration_hours = negative_frames / fps / 3600 if negative_frames else 0.0
    return {
        "evaluation_type": "negative_frame_proxy",
        "source": "validation images with empty labels",
        "negative_frames": int(negative_frames),
        "false_alarm_frames": false_alarm_frames,
        "fps_assumption": fps,
        "duration_hours": duration_hours,
        "false_alarm_per_hour": false_alarm_frames / duration_hours if duration_hours else 0.0,
        "confidence": confidence,
        "note": "No standalone negative video files were present in data/; treat this as a proxy, not camera-video ground truth.",
    }


def evaluate_model(args: argparse.Namespace, model_id: str) -> dict:
    run_dir = MODEL_RUNS[model_id]
    checkpoint = run_dir / "weights/best.pt"
    if not checkpoint.exists():
        raise FileNotFoundError(checkpoint)
    output_dir = args.output_root / model_id
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_root = args.dataset_root
    cache_dir = output_dir / ".cache"
    cache_paths: dict[str, Path] = {}
    split_counts: dict[str, int] = {}
    started = time.time()
    for split in ("val", "test"):
        image_root = dataset_root / "images" / split
        label_root = dataset_root / "labels" / split
        image_paths = sorted(image_root.glob("*.jpg")) + sorted(image_root.glob("*.jpeg")) + sorted(image_root.glob("*.png"))
        if not image_paths:
            raise FileNotFoundError(f"No images found in {image_root}")
        if args.limit:
            image_paths = image_paths[: args.limit]
        cache_path = cache_dir / f"{split}.jsonl"
        print(f"[{model_id}] predicting {split}: {len(image_paths)} images", flush=True)
        split_counts[split] = collect_predictions(
            checkpoint,
            image_paths,
            label_root,
            args.imgsz,
            args.batch,
            args.device,
            args.nms_iou,
            args.prediction_conf,
            cache_path,
        )
        cache_paths[split] = cache_path
        # Do not keep a second split's records or model state in memory.
        gc.collect()

    sweep_rows = []
    for confidence in args.confidences:
        sweep_rows.append({"split": "val", **threshold_metrics(iter_cached_records(cache_paths["val"]), confidence, args.match_iou)})
    write_csv(output_dir / "threshold_sweep.csv", sweep_rows)
    best = max(
        (row for row in sweep_rows if row["split"] == "val"),
        key=lambda row: (row["f1"], row["recall"], row["precision"], -row["confidence"]),
    )
    locked_confidence = float(best["confidence"])
    val_locked = threshold_metrics(iter_cached_records(cache_paths["val"]), locked_confidence, args.match_iou) | map_metrics(cache_paths["val"])
    test_locked = threshold_metrics(iter_cached_records(cache_paths["test"]), locked_confidence, args.match_iou) | map_metrics(cache_paths["test"])
    size_rows = evaluate_size_bins(iter_cached_records(cache_paths["test"]), locked_confidence, args.match_iou)
    write_csv(output_dir / "size_bin_metrics.csv", size_rows)
    negative = negative_proxy_from_cache(cache_paths["val"], locked_confidence, args.negative_fps)
    write_csv(output_dir / "negative_video_metrics.csv", [negative])
    metrics_rows = [
        {"split": "val", **{key: value for key, value in val_locked.items() if not isinstance(value, dict)}},
        {"split": "test", **{key: value for key, value in test_locked.items() if not isinstance(value, dict)}},
    ]
    write_csv(output_dir / "metrics.csv", metrics_rows)
    metrics = {
        "model_id": model_id,
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": sha256_file(checkpoint),
        "locked_confidence": locked_confidence,
        "nms_iou": args.nms_iou,
        "match_iou": args.match_iou,
        "size_definition": "max(bbox_width,bbox_height) in original image pixels",
        "val": val_locked,
        "test": test_locked,
        "negative_video": negative,
        "split_counts": split_counts,
        "multi_seed_status": "unavailable: Phase 2 contains seed 42 only",
        "elapsed_seconds": time.time() - started,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    provenance = {
        "model_id": model_id,
        "checkpoint_sha256": metrics["checkpoint_sha256"],
        "dataset_manifest_sha256": sha256_file(dataset_root / "manifest.json"),
        "split_registry_sha256": sha256_file(dataset_root / "split_registry.json"),
        "evaluation_config": {
            "imgsz": args.imgsz,
            "batch": args.batch,
            "device": args.device,
            "confidences": args.confidences,
            "prediction_conf_floor": args.prediction_conf,
            "nms_iou": args.nms_iou,
            "match_iou": args.match_iou,
            "negative_fps": args.negative_fps,
        },
        "python": platform.python_version(),
        "git": git_state(),
        "command": " ".join(args.original_command),
        "started_at_unix": started,
        "finished_at_unix": time.time(),
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    # Cache is an intermediate artifact, not a release output.  Remove it only
    # after all reports have been written; an interrupted run leaves it for
    # diagnosis and can be safely discarded on the next clean run.
    for cache_path in cache_paths.values():
        cache_path.unlink(missing_ok=True)
    try:
        cache_dir.rmdir()
    except OSError:
        pass
    return metrics


def write_model_report(output_dir: Path, metrics: dict, rank: int, winner: str) -> None:
    val = metrics["val"]
    test = metrics["test"]
    report = f"""# Model selection — {metrics['model_id']}

Status: `DONE`

## Locked protocol

- Threshold was selected on validation only: `{metrics['locked_confidence']:.2f}`.
- NMS IoU: `{metrics['nms_iou']:.2f}`; matching IoU: `{metrics['match_iou']:.2f}`.
- Test was evaluated only after the validation threshold was locked.
- Size bin uses `max(bbox_width, bbox_height)` in original-image pixels.

## Results

| Split | Precision | Recall | F1 | mAP50 | mAP50-95 | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| Validation | {val['precision']:.4f} | {val['recall']:.4f} | {val['f1']:.4f} | {val['mAP50']:.4f} | {val['mAP50-95']:.4f} | {val['fp']} | {val['fn']} |
| Test | {test['precision']:.4f} | {test['recall']:.4f} | {test['f1']:.4f} | {test['mAP50']:.4f} | {test['mAP50-95']:.4f} | {test['fp']} | {test['fn']} |

## Decision

- Validation rank: `{rank}`.
- Overall winner: `{winner}`.
- This checkpoint is not selected solely by mAP; precision/recall/F1, size-bin recall,
  false-alarm proxy and deployability are considered together.
- Multi-seed variance is unavailable because Phase 2 currently has seed 42 only.
- `negative_video_metrics.csv` is a negative-frame proxy because no standalone video
  files were present; a real camera/video run is required before release.

Checkpoint SHA256: `{metrics['checkpoint_sha256']}`
"""
    (output_dir / "MODEL_SELECTION.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("data/processed/drone-single-class"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/benchmarks/model-selection"))
    parser.add_argument("--models", nargs="+", choices=sorted(MODEL_RUNS), default=sorted(MODEL_RUNS))
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--device", default="0")
    parser.add_argument("--nms-iou", type=float, default=0.70)
    parser.add_argument("--match-iou", type=float, default=0.50)
    parser.add_argument("--negative-fps", type=float, default=30.0)
    parser.add_argument("--conf-start", type=float, default=0.05)
    parser.add_argument("--conf-end", type=float, default=0.60)
    parser.add_argument("--conf-step", type=float, default=0.05)
    parser.add_argument(
        "--prediction-conf",
        type=float,
        default=0.05,
        help="Confidence floor retained during prediction; keep >= threshold sweep start to bound RAM.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit images per split for a smoke test; 0 means all images.")
    args = parser.parse_args()
    args.original_command = ["python", *(__import__("sys").argv)]
    args.dataset_root = args.dataset_root.resolve()
    args.output_root = args.output_root.resolve()
    args.confidences = [
        round(float(value), 4)
        for value in np.arange(args.conf_start, args.conf_end + args.conf_step / 2, args.conf_step)
    ]
    if not (args.dataset_root / "manifest.json").exists():
        raise FileNotFoundError(args.dataset_root / "manifest.json")
    all_metrics = []
    for model_id in args.models:
        all_metrics.append(evaluate_model(args, model_id))
    # Selection uses validation only. F1 is primary, recall is the first tiebreak;
    # this avoids opening test results as a tuning signal.
    ranked = sorted(all_metrics, key=lambda item: (item["val"]["f1"], item["val"]["recall"], item["val"]["precision"]), reverse=True)
    winner = ranked[0]["model_id"]
    for rank, metrics in enumerate(ranked, start=1):
        write_model_report(args.output_root / metrics["model_id"], metrics, rank, winner)
    global_report = [
        "# Phase 3 model selection",
        "",
        "Status: `DONE_WITH_RECORDED_LIMITATIONS`",
        "",
        f"Winner: `{winner}`",
        "",
        "The winner and threshold were selected using validation only; test metrics were "
        "computed afterward with the locked threshold.",
        "",
        "| Rank | Model | Val F1 | Val Recall | Val Precision | Locked conf | Test F1 |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for rank, metrics in enumerate(ranked, start=1):
        global_report.append(
            f"| {rank} | {metrics['model_id']} | {metrics['val']['f1']:.4f} | "
            f"{metrics['val']['recall']:.4f} | {metrics['val']['precision']:.4f} | "
            f"{metrics['locked_confidence']:.2f} | {metrics['test']['f1']:.4f} |"
        )
    global_report += [
        "",
        "Limitations: Phase 2 has seed 42 only, and no standalone negative video was "
        "present; negative-video output is explicitly a negative-frame proxy.",
    ]
    (args.output_root / "MODEL_SELECTION.md").write_text("\n".join(global_report) + "\n", encoding="utf-8")
    (args.output_root / "phase3_summary.json").write_text(
        json.dumps({"status": "DONE_WITH_RECORDED_LIMITATIONS", "winner": winner, "models": [m["model_id"] for m in ranked]}, indent=2),
        encoding="utf-8",
    )
    print(f"Phase 3 complete. Winner: {winner}", flush=True)


if __name__ == "__main__":
    main()
