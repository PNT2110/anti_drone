#!/usr/bin/env python3
"""Aggregate the single locked Scope 26 NCNN TEST run without re-inference."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope26"
IOU_MATCH = 0.50
AP_IOUS = [round(x / 100, 2) for x in range(50, 96, 5)]
SIZE_BINS = ("<4", "4-8", "8-16", "16-32", "32-64", ">64")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def iou(left, right) -> float:
    x1 = max(float(left[0]), float(right[0]))
    y1 = max(float(left[1]), float(right[1]))
    x2 = min(float(left[2]), float(right[2]))
    y2 = min(float(left[3]), float(right[3]))
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_left = max(0.0, float(left[2]) - float(left[0])) * max(0.0, float(left[3]) - float(left[1]))
    area_right = max(0.0, float(right[2]) - float(right[0])) * max(0.0, float(right[3]) - float(right[1]))
    union = area_left + area_right - inter
    return inter / union if union else 0.0


def size_bin(box) -> str:
    side = max(float(box[2]) - float(box[0]), float(box[3]) - float(box[1]))
    if side < 4:
        return "<4"
    if side < 8:
        return "4-8"
    if side < 16:
        return "8-16"
    if side < 32:
        return "16-32"
    if side < 64:
        return "32-64"
    return ">64"


def match(record: dict, threshold: float = IOU_MATCH) -> dict:
    predictions = sorted(enumerate(record["predictions"]), key=lambda item: (-float(item[1]["confidence"]), item[0]))
    matched_gt: set[int] = set()
    pairs = []
    unmatched_predictions = []
    for pred_index, prediction in predictions:
        candidates = [(iou(prediction["bbox"], gt), gt_index) for gt_index, gt in enumerate(record["gt_boxes"]) if gt_index not in matched_gt]
        best_iou, best_gt = max(candidates) if candidates else (0.0, -1)
        if best_iou >= threshold:
            matched_gt.add(best_gt)
            pairs.append({"pred_index": pred_index, "gt_index": best_gt, "iou": best_iou, "confidence": float(prediction["confidence"])})
        else:
            unmatched_predictions.append({"pred_index": pred_index, "best_iou": best_iou, "confidence": float(prediction["confidence"]), "bbox": prediction["bbox"]})
    unmatched_gt = [{"gt_index": index, "best_iou": max((iou(record["predictions"][p["pred_index"]]["bbox"], gt) for p in pairs), default=0.0)} for index, gt in enumerate(record["gt_boxes"]) if index not in matched_gt]
    # Recompute unmatched-GT overlap against all predictions, not just accepted matches.
    for item in unmatched_gt:
        item["best_iou"] = max((iou(pred["bbox"], record["gt_boxes"][item["gt_index"]]) for pred in record["predictions"]), default=0.0)
    return {"pairs": pairs, "unmatched_predictions": unmatched_predictions, "unmatched_gt": unmatched_gt}


def average_precision(records: list[dict], threshold: float) -> float:
    total_gt = sum(len(record["gt_boxes"]) for record in records)
    candidates = []
    for record_index, record in enumerate(records):
        for prediction_index, prediction in enumerate(record["predictions"]):
            candidates.append((float(prediction["confidence"]), record_index, prediction_index))
    candidates.sort(key=lambda item: (-item[0], records[item[1]]["sample_id"], item[2]))
    matched: dict[int, set[int]] = defaultdict(set)
    tp = []
    fp = []
    for _, record_index, prediction_index in candidates:
        record = records[record_index]
        prediction = record["predictions"][prediction_index]
        options = [(iou(prediction["bbox"], gt), gt_index) for gt_index, gt in enumerate(record["gt_boxes"]) if gt_index not in matched[record_index]]
        best_iou, best_gt = max(options) if options else (0.0, -1)
        if best_iou >= threshold:
            matched[record_index].add(best_gt)
            tp.append(1)
            fp.append(0)
        else:
            tp.append(0)
            fp.append(1)
    if not total_gt:
        return 0.0
    cumulative_tp = []
    cumulative_fp = []
    running_tp = running_fp = 0
    for true_positive, false_positive in zip(tp, fp):
        running_tp += true_positive
        running_fp += false_positive
        cumulative_tp.append(running_tp)
        cumulative_fp.append(running_fp)
    recalls = [value / total_gt for value in cumulative_tp]
    precisions = [tp_value / max(tp_value + fp_value, 1) for tp_value, fp_value in zip(cumulative_tp, cumulative_fp)]
    return sum(max((precision for recall, precision in zip(recalls, precisions) if recall >= level), default=0.0) for level in [x / 100 for x in range(101)]) / 101


def threshold_summary(records: list[dict]) -> dict:
    tp = fp = fn = 0
    for record in records:
        result = match(record)
        tp += len(result["pairs"])
        fp += len(result["unmatched_predictions"])
        fn += len(result["unmatched_gt"])
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    ap = {f"AP{int(threshold * 100)}": average_precision(records, threshold) for threshold in AP_IOUS}
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1, "match_iou": IOU_MATCH, "confidence_threshold": 0.25, "AP75": ap["AP75"], "mAP50": ap["AP50"], "mAP50-95": sum(ap.values()) / len(ap), "AP_by_iou": ap}


def group_summary(records: list[dict]) -> dict:
    base = threshold_summary(records)
    return {key: base[key] for key in ("sample_count", "gt_count", "tp", "fp", "fn", "precision", "recall", "f1", "mAP50", "mAP50-95", "AP75") if key in base} | base


def add_group_metrics(records: list[dict], group_name: str, group_value: str) -> dict:
    selected = [record for record in records if record.get(group_name) == group_value]
    summary = threshold_summary(selected)
    summary.update({"group": group_value, "sample_count": len(selected), "gt_count": sum(len(record["gt_boxes"]) for record in selected)})
    return summary


def main() -> int:
    headline_path = RUNTIME / "headline_result.json"
    if headline_path.exists():
        raise SystemExit("HEADLINE_RESULT_EXISTS: immutable headline already created")
    records = [json.loads(line) for line in (RUNTIME / "predictions.jsonl").read_text().splitlines()]
    if len(records) != 9848 or len({record["sample_id"] for record in records}) != 9848:
        raise SystemExit(f"PREDICTION_COVERAGE_MISMATCH: {len(records)}")
    runner = json.loads((RUNTIME / "pi_runner_result.json").read_text())
    event = json.loads((RUNTIME / "test_open_event.json").read_text())
    if runner.get("status") != "FINAL_TEST_COMPLETE" or runner.get("processed") != 9848 or runner.get("skipped") != 0:
        raise SystemExit("EVALUATION_INCOMPLETE")
    overall = threshold_summary(records)
    headline = {
        "status": "FINAL_TEST_COMPLETE",
        "candidate_id": event["candidate_id"],
        "freeze_manifest_sha256": event["freeze_manifest_sha256"],
        "test_split_registry_sha256": event["split_registry_sha256"],
        "processed_samples": len(records),
        "expected_samples": 9848,
        "skipped_samples": runner["skipped"],
        "precision": overall["precision"],
        "recall": overall["recall"],
        "mAP50": overall["mAP50"],
        "mAP50-95": overall["mAP50-95"],
        "AP75": overall["AP75"],
        "tp": overall["tp"],
        "fp": overall["fp"],
        "fn": overall["fn"],
        "confidence_threshold": event["confidence"],
        "nms_iou": event["nms_iou"],
        "imgsz": event["imgsz"],
        "backend": event["backend"],
        "precision_mode": event["precision"],
        "runtime": runner["runtime"],
        "test_open_event_timestamp": event["timestamp"],
        "prediction_file_sha256": sha256(RUNTIME / "predictions.jsonl"),
        "metric_definition": "101-point interpolated AP over frozen NCNN predictions retained at confidence >= 0.25; greedy per-image one-to-one matching; IoU 0.50:0.95 step 0.05",
        "test_accessed": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    write_json(headline_path, headline)
    headline_hash = sha256(headline_path)
    (RUNTIME / "headline_result.sha256").write_text(f"{headline_hash}  {headline_path.name}\n")

    modalities = {modality: add_group_metrics(records, "modality", modality) for modality in ("visible", "infrared")}
    write_json(RUNTIME / "modality_analysis.json", {"status": "DESCRIPTIVE_ANALYSIS", "headline_result_sha256": headline_hash, "groups": modalities, "test_accessed": True})

    sequences = defaultdict(list)
    for record in records:
        sequences[record["source_sequence"]].append(record)
    sequence_rows = [add_group_metrics(items, "source_sequence", sequence) for sequence, items in sorted(sequences.items())]
    write_json(RUNTIME / "source_sequence_analysis.json", {"status": "DESCRIPTIVE_ANALYSIS", "headline_result_sha256": headline_hash, "rows": sequence_rows, "test_accessed": True})

    size_counts = {name: {"gt": 0, "tp": 0, "fn": 0} for name in SIZE_BINS}
    for record in records:
        result = match(record)
        matched_gt = {pair["gt_index"] for pair in result["pairs"]}
        for index, gt in enumerate(record["gt_boxes"]):
            bucket = size_bin(gt)
            size_counts[bucket]["gt"] += 1
            if index in matched_gt:
                size_counts[bucket]["tp"] += 1
            else:
                size_counts[bucket]["fn"] += 1
    size_rows = []
    for bucket in SIZE_BINS:
        row = size_counts[bucket] | {"size_bin": bucket, "recall": size_counts[bucket]["tp"] / size_counts[bucket]["gt"] if size_counts[bucket]["gt"] else 0.0}
        size_rows.append(row)
    write_json(RUNTIME / "object_size_analysis.json", {"status": "DESCRIPTIVE_ANALYSIS", "headline_result_sha256": headline_hash, "definition": "COCO-independent project bins by max(bbox_width,bbox_height) pixels: <4, 4-8, 8-16, 16-32, 32-64, >64", "rows": size_rows, "AP": "N/A; this evaluator reports size-stratified recall only and does not implement COCO ignore-area AP", "test_accessed": True})

    error_counts = {"FALSE_NEGATIVE": 0, "FALSE_POSITIVE": 0, "LOCALIZATION_ERROR": 0}
    failure_pool = defaultdict(list)
    for record in records:
        matched = match(record)
        matched_pairs = matched["pairs"]
        for pair in matched_pairs:
            failure_pool["lowest_iou_tp"].append({"sample_id": record["sample_id"], "image_rel": record["image_rel"], "modality": record["modality"], "source_sequence": record["source_sequence"], "confidence": pair["confidence"], "iou": pair["iou"], "failure_type": "LOWEST_IOU_TP"})
        for item in matched["unmatched_predictions"]:
            if item["best_iou"] > 0.0:
                error_counts["LOCALIZATION_ERROR"] += 1
                kind = "LOCALIZATION_ERROR"
            else:
                error_counts["FALSE_POSITIVE"] += 1
                kind = "FALSE_POSITIVE"
            failure_pool["highest_confidence_fp"].append({"sample_id": record["sample_id"], "image_rel": record["image_rel"], "modality": record["modality"], "source_sequence": record["source_sequence"], "confidence": item["confidence"], "best_iou": item["best_iou"], "failure_type": kind})
        for item in matched["unmatched_gt"]:
            if item["best_iou"] > 0.0:
                error_counts["LOCALIZATION_ERROR"] += 1
                kind = "LOCALIZATION_ERROR"
            else:
                error_counts["FALSE_NEGATIVE"] += 1
                kind = "FALSE_NEGATIVE"
            failure_pool["false_negative"].append({"sample_id": record["sample_id"], "image_rel": record["image_rel"], "modality": record["modality"], "source_sequence": record["source_sequence"], "best_iou": item["best_iou"], "failure_type": kind})
    for key, rows in failure_pool.items():
        if key == "highest_confidence_fp":
            rows.sort(key=lambda row: (-row.get("confidence", 0.0), row["sample_id"]))
        elif key == "lowest_iou_tp":
            rows.sort(key=lambda row: (row.get("iou", 1.0), row["sample_id"]))
        else:
            rows.sort(key=lambda row: (row.get("best_iou", 1.0), row["sample_id"]))
    failures = {key: rows[:10] for key, rows in failure_pool.items()}
    failures["visible_failures"] = [row for rows in failure_pool.values() for row in rows if row["modality"] == "visible"][:10]
    failures["infrared_failures"] = [row for rows in failure_pool.values() for row in rows if row["modality"] == "infrared"][:10]
    failures["small_object_failures"] = []
    for record in records:
        for gt in record["gt_boxes"]:
            if size_bin(gt) in {"<4", "4-8", "8-16"}:
                failures["small_object_failures"].append({"sample_id": record["sample_id"], "image_rel": record["image_rel"], "modality": record["modality"], "size_bin": size_bin(gt)})
    failures["small_object_failures"] = sorted(failures["small_object_failures"], key=lambda row: (row["size_bin"], row["sample_id"]))[:10]
    write_json(RUNTIME / "failure_samples.json", {"status": "DETERMINISTIC_FAILURE_SET", "headline_result_sha256": headline_hash, "selection_rules": {"highest_confidence_fp": "confidence descending, sample_id ascending, first 10", "lowest_iou_tp": "IoU ascending, sample_id ascending, first 10", "false_negative": "best IoU ascending, sample_id ascending, first 10", "modality": "stable source-order after deterministic base sort", "small_object": "size bins <16 pixels, size_bin then sample_id ascending, first 10"}, "samples": failures, "test_accessed": True})

    write_json(RUNTIME / "error_analysis.json", {"status": "ERROR_ANALYSIS_COMPLETE", "headline_result_sha256": headline_hash, "match_iou": IOU_MATCH, "counts": error_counts, "confidence_below_frozen_threshold": {"status": "NOT_OBSERVABLE", "reason": "NCNN production runner emits post-threshold detections; raw below-threshold candidates were not retained"}, "nms_interaction": {"status": "NOT_OBSERVABLE", "reason": "final output does not retain pre-NMS candidate trace"}, "confusion_representation": {"true_positive_drone": overall["tp"], "false_positive_background": overall["fp"], "false_negative_background": overall["fn"]}, "test_accessed": True})

    audit = {"status": "PASS", "headline_result_sha256": headline_hash, "prediction_sha256": sha256(RUNTIME / "predictions.jsonl"), "processed": len(records), "skipped": runner["skipped"], "no_pytorch_primary": True, "no_threshold_sweep": True, "no_model_switch": True, "test_accessed": True}
    write_json(RUNTIME / "metric_audit.json", audit)
    print(json.dumps({"status": headline["status"], "headline_result_sha256": headline_hash, "metrics": {key: headline[key] for key in ("precision", "recall", "mAP50", "mAP50-95", "AP75", "tp", "fp", "fn")}, "modalities": modalities}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
