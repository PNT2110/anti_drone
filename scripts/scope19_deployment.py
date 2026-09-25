"""Scope 19 deployment/export audit without opening the V3 test split.

All deployment inputs are synthetic or selected from the repaired V3 train
split.  The six Scope 18 validation records are read from the frozen ledger;
no validation or test accuracy is recomputed here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import statistics
import tempfile
import time
from pathlib import Path
from typing import Iterable



ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
OUTPUT = ROOT / "artifacts/exports/scope19"
RUNTIME = ROOT / ".runtime/scope19"
LEDGER = ROOT / ".runtime/scope18/run_ledger.json"
ORDER = [("yolov8n", 640), ("yolov8n", 480), ("yolov11n", 640), ("yolov11n", 480), ("yolo26n", 640), ("yolo26n", 480)]
EXPECTED_BEST = {
    "scope18-yolov8n-640": "debcef45f0a1667f16c62daf7a8f42d0e5932be498b549b2f985bc72915e9718",
    "scope18-yolov8n-480": "359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e",
    "scope18-yolov11n-640": "ab2d146424a2c9c0ce053b122463d7d2e796834e9671a60bdeacd4047ca68186",
    "scope18-yolov11n-480": "6f086a2206a466c1037e6aab3ddbbf1afc40b38f7643e9be4f83a85630a81e05",
    "scope18-yolo26n-640": "3153d0ffdd6b4db7b3fd28fa4026636fe3ffad19acaedbea1c4f35c996fb8bae",
    "scope18-yolo26n-480": "1500fb46bbf01910f85a0b75b37e00f275bf0cb725c0829e7c2db293ea6a23d6",
}
TOLERANCE = {"confidence_abs": 0.05, "bbox_iou_min": 0.95, "class_exact": True}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    else:
        for item in sorted(path.rglob("*")):
            if item.is_file():
                digest.update(str(item.relative_to(path)).encode())
                with item.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def checkpoint_path(run_id: str) -> Path:
    return ROOT / "artifacts/experiments/scope18-v3-labelrepair" / run_id / "attempt-batch16/weights/best.pt"


def validate_output_path(path: Path, checkpoint: Path) -> bool:
    return path.resolve() != checkpoint.resolve() and OUTPUT.resolve() in path.resolve().parents


def fixed_train_images(count: int = 8) -> list[Path]:
    images = sorted((DATASET / "images/train").glob("*.jpg"))
    if len(images) < count:
        raise RuntimeError(f"train benchmark subset has only {len(images)} images")
    return images[:count]


def calibration_images(count: int = 128) -> list[Path]:
    images = sorted((DATASET / "images/train").glob("*.jpg"))
    if len(images) < count:
        raise RuntimeError(f"train calibration subset has only {len(images)} images")
    return images[:count]


def audit_inputs() -> dict:
    errors: list[str] = []
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    if ledger.get("test_used") is not False:
        errors.append("Scope 18 ledger does not explicitly lock test_used=false")
    runs = {item["run_id"]: item for item in ledger.get("runs", [])}
    checkpoints = {}
    for model_id, imgsz in ORDER:
        run_id = f"scope18-{model_id}-{imgsz}"
        record = runs.get(run_id)
        path = checkpoint_path(run_id)
        actual = sha256(path) if path.is_file() else None
        checkpoints[run_id] = {"path": str(path), "exists": path.is_file(), "sha256": actual, "expected": EXPECTED_BEST[run_id], "match": actual == EXPECTED_BEST[run_id], "scope18_status": record.get("status") if record else None}
        if actual != EXPECTED_BEST[run_id] or not record or record.get("status") != "COMPLETE":
            errors.append(f"checkpoint or frozen ledger mismatch: {run_id}")
    images = fixed_train_images()
    calibration = calibration_images()
    input_manifest = {"status": "PASS", "split": "train", "test_accessed": False, "count": len(images), "sample_ids": [item.name for item in images], "paths": [str(item) for item in images], "imgsz_by_run": {f"scope18-{m}-{s}": s for m, s in ORDER}}
    calib_manifest = {"status": "PASS", "source_split": "train", "test_accessed": False, "count": len(calibration), "sample_ids": [item.name for item in calibration], "paths": [str(item) for item in calibration], "selection": "lexicographically first fixed train-only subset; no accuracy selection"}
    write_json(RUNTIME / "benchmark_input_manifest.json", input_manifest)
    write_json(RUNTIME / "calibration_manifest.json", calib_manifest)
    result = {"status": "PASS" if not errors else "BLOCKED", "errors": errors, "dataset": str(DATASET), "dataset_manifest_sha256": sha256(DATASET / "manifest.json"), "dataset_split_registry_sha256": sha256(DATASET / "split_registry.json"), "test_accessed": False, "checkpoints": checkpoints, "frozen_validation_source": str(LEDGER), "benchmark_input_manifest": str(RUNTIME / "benchmark_input_manifest.json"), "calibration_manifest": str(RUNTIME / "calibration_manifest.json"), "test_policy": "locked; no test images, test inference or test accuracy"}
    write_json(RUNTIME / "input_audit.json", result)
    return result


def frozen_rows() -> list[dict]:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    return ledger["runs"]


def copy_export(source: Path, target: Path) -> Path:
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            destination = target / item.name
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def model_characteristics(checkpoint: Path, imgsz: int) -> dict:
    from ultralytics import YOLO

    model = YOLO(str(checkpoint))
    parameters = sum(parameter.numel() for parameter in model.model.parameters())
    return {"parameter_count": int(parameters), "flops": None, "flops_status": "framework did not return a machine-readable value"}


def export_one(run_id: str, runtime: str, int8: bool, calibration_yaml: Path | None) -> dict:
    from ultralytics import YOLO

    checkpoint = checkpoint_path(run_id)
    model_id, imgsz = run_id.removeprefix("scope18-").rsplit("-", 1)
    target = OUTPUT / run_id / ("int8" if int8 else "float32") / runtime
    target.mkdir(parents=True, exist_ok=True)
    if not validate_output_path(target, checkpoint):
        return {"status": "BLOCKED", "error": "unsafe export output path", "path": str(target)}
    item = {"run_id": run_id, "runtime": runtime, "quantization": "int8" if int8 else "float32", "status": "BLOCKED", "target": str(target), "warnings": []}
    with tempfile.TemporaryDirectory(prefix="scope19-export-") as temp:
        temp_model = Path(temp) / "model.pt"
        shutil.copy2(checkpoint, temp_model)
        try:
            model = YOLO(str(temp_model))
            args = {"format": runtime, "imgsz": int(imgsz), "batch": 1, "dynamic": False, "simplify": True, "nms": False, "device": "cpu"}
            if runtime == "onnx":
                args["opset"] = 12
            if int8:
                if runtime != "tflite":
                    item.update({"status": "INT8_UNSUPPORTED", "error": f"Scope19 int8 pipeline supports tflite only, not {runtime}"})
                    return item
                args.update({"int8": True, "data": str(calibration_yaml), "fraction": 1.0})
            result = model.export(**args)
            exported = Path(str(result))
            if not exported.exists():
                raise FileNotFoundError(exported)
            destination = target / ("model" + exported.suffix if exported.is_file() else "model_export")
            final = copy_export(exported, destination)
            item.update({"status": "EXPORTED", "path": str(final), "sha256": sha256(final), "size_bytes": sum(p.stat().st_size for p in final.rglob("*") if p.is_file()) if final.is_dir() else final.stat().st_size, "input_shape": [1, 3, int(imgsz), int(imgsz)], "static_shape": True, "output_contract": "Ultralytics exported detect graph; backend-specific tensor contract recorded by exporter"})
        except Exception as exc:
            item.update({"status": "BLOCKED", "error": f"{type(exc).__name__}: {exc}"})
            (target / "EXPORT_BLOCKED.txt").write_text(item["error"] + "\n", encoding="utf-8")
    return item


def export_all(audit: dict) -> dict:
    if audit["status"] != "PASS":
        result = {"status": "BLOCKED_INPUT", "exports": []}
        write_json(RUNTIME / "export_report.json", result)
        return result
    exports = []
    for model_id, imgsz in ORDER:
        run_id = f"scope18-{model_id}-{imgsz}"
        for runtime in ("onnx", "ncnn", "tflite"):
            exports.append(export_one(run_id, runtime, False, None))
    calibration_yaml = RUNTIME / "int8_calibration.yaml"
    calibration_list = RUNTIME / "int8_calibration_train.txt"
    calibration_list.write_text("\n".join(str(p) for p in calibration_images()) + "\n", encoding="utf-8")
    calibration_yaml.write_text(f"path: /\ntrain: {calibration_list}\nval: {calibration_list}\nnames:\n  0: drone\n", encoding="utf-8")
    int8 = []
    for model_id, imgsz in ORDER:
        int8.append(export_one(f"scope18-{model_id}-{imgsz}", "tflite", True, calibration_yaml))
    result = {"status": "PASS" if all(item.get("status") == "EXPORTED" for item in exports) else "PARTIALLY_COMPLETE", "exports": exports, "int8": int8, "calibration": {"yaml": str(calibration_yaml), "manifest": str(RUNTIME / "calibration_manifest.json"), "source_split": "train", "count": len(calibration_images())}}
    write_json(RUNTIME / "export_report.json", result)
    return result


def detections(model: object, image: Path, imgsz: int) -> list[dict]:
    result = model.predict(source=str(image), imgsz=imgsz, conf=0.25, iou=0.70, device="cpu", verbose=False)[0]
    if result.boxes is None:
        return []
    rows = []
    for box, confidence, class_id in zip(result.boxes.xyxy.cpu().numpy(), result.boxes.conf.cpu().numpy(), result.boxes.cls.cpu().numpy()):
        rows.append({"class": int(class_id), "confidence": float(confidence), "bbox": [float(v) for v in box]})
    return sorted(rows, key=lambda row: (-row["confidence"], row["class"], row["bbox"]))


def box_iou(left: Iterable[float], right: Iterable[float]) -> float:
    ax1, ay1, ax2, ay2 = left
    bx1, by1, bx2, by2 = right
    ix1, iy1, ix2, iy2 = max(ax1, bx1), max(ay1, by1), min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union else 1.0 if area_a == area_b == 0 else 0.0


def compare_detections(reference: list[dict], candidate: list[dict], tolerance: dict = TOLERANCE) -> dict:
    result = {"status": "PASS", "reference_count": len(reference), "candidate_count": len(candidate), "class_exact": True, "max_confidence_abs": 0.0, "min_bbox_iou": 1.0, "tolerance": tolerance}
    if len(reference) != len(candidate):
        result["status"] = "BACKEND_PARITY_FAIL"
    for left, right in zip(reference, candidate):
        result["class_exact"] = result["class_exact"] and left["class"] == right["class"]
        result["max_confidence_abs"] = max(result["max_confidence_abs"], abs(left["confidence"] - right["confidence"]))
        result["min_bbox_iou"] = min(result["min_bbox_iou"], box_iou(left["bbox"], right["bbox"]))
    if not result["class_exact"] or result["max_confidence_abs"] > tolerance["confidence_abs"] or result["min_bbox_iou"] < tolerance["bbox_iou_min"]:
        result["status"] = "BACKEND_PARITY_FAIL"
    return result


def parity_and_benchmark(audit: dict, export_report: dict) -> dict:
    import numpy as np
    import psutil

    from ultralytics import YOLO

    if audit["status"] != "PASS":
        result = {"status": "BLOCKED_INPUT"}
        write_json(RUNTIME / "backend_parity.json", result)
        return result
    images = fixed_train_images()
    all_parity = []
    benchmark = []
    for model_id, imgsz in ORDER:
        run_id = f"scope18-{model_id}-{imgsz}"
        checkpoint = checkpoint_path(run_id)
        reference_model = YOLO(str(checkpoint))
        for runtime in ("onnx", "ncnn", "tflite"):
            record = next((x for x in export_report.get("exports", []) if x.get("run_id") == run_id and x.get("runtime") == runtime), None)
            parity_item = {"run_id": run_id, "runtime": runtime, "input_split": "train", "test_accessed": False, "status": "BACKEND_PARITY_FAIL"}
            if not record or record.get("status") != "EXPORTED":
                parity_item["error"] = "export unavailable"
                all_parity.append(parity_item)
                continue
            try:
                candidate_path = Path(record["path"])
                # Ultralytics detects NCNN directories by the *_ncnn_model suffix.
                # Keep the exported artifact immutable and create a local loader alias.
                if runtime == "ncnn" and candidate_path.is_dir() and candidate_path.name == "model_export":
                    alias = candidate_path.parent / "model_ncnn_model"
                    if not alias.exists():
                        shutil.copytree(candidate_path, alias)
                    candidate_path = alias
                candidate_model = YOLO(str(candidate_path))
                comparisons = []
                for image in images:
                    comparisons.append(compare_detections(detections(reference_model, image, imgsz), detections(candidate_model, image, imgsz)))
                parity_item.update({"status": "PASS" if all(x["status"] == "PASS" for x in comparisons) else "BACKEND_PARITY_FAIL", "comparisons": comparisons, "tolerance": TOLERANCE})
                # Runtime speed is measured independently of parity. A parity failure
                # must be reported, but it must not hide a usable host timing result.
                samples = images
                for _ in range(20):
                    for image in samples:
                        candidate_model.predict(source=str(image), imgsz=imgsz, conf=0.25, iou=0.70, device="cpu", verbose=False)
                latencies = []
                rss_values = []
                process = psutil.Process()
                for index in range(100):
                    image = samples[index % len(samples)]
                    started = time.perf_counter()
                    candidate_model.predict(source=str(image), imgsz=imgsz, conf=0.25, iou=0.70, device="cpu", verbose=False)
                    latencies.append((time.perf_counter() - started) * 1000.0)
                    rss_values.append(process.memory_info().rss)
                benchmark.append({"run_id": run_id, "runtime": runtime, "input_split": "train", "test_accessed": False, "imgsz": imgsz, "warmup_iterations": 20 * len(samples), "measured_iterations": 100, "mean_latency_ms": statistics.mean(latencies), "median_latency_ms": float(np.percentile(latencies, 50)), "p95_latency_ms": float(np.percentile(latencies, 95)), "fps_mean": 1000.0 / statistics.mean(latencies), "rss_peak_bytes": max(rss_values), "cpu_only_host_reference": True, "pi5_measured": False, "parity_status": parity_item["status"], "status": "HOST_REFERENCE_ONLY"})
            except Exception as exc:
                parity_item["error"] = f"{type(exc).__name__}: {exc}"
            all_parity.append(parity_item)
    result = {"status": "PASS" if all(x["status"] == "PASS" for x in all_parity) else "PARTIALLY_COMPLETE", "protocol": {"source_split": "train", "test_accessed": False, "tolerance": TOLERANCE, "confidence": 0.25, "nms_iou": 0.70}, "parity": all_parity, "benchmark": benchmark, "pi5_status": "BLOCKED_NO_RASPBERRY_PI_5_IN_WORKSPACE"}
    write_json(RUNTIME / "backend_parity.json", {"status": result["status"], "protocol": result["protocol"], "parity": all_parity})
    write_json(RUNTIME / "host_benchmark.json", {"status": "HOST_REFERENCE_ONLY", "protocol": result["protocol"], "records": benchmark})
    return result


def selection_table(audit: dict, export_report: dict, deployment: dict) -> dict:
    frozen = {row["run_id"]: row for row in frozen_rows()}
    records = []
    for model_id, imgsz in ORDER:
        run_id = f"scope18-{model_id}-{imgsz}"
        validation = frozen.get(run_id, {}).get("validation_metrics", {})
        best_epoch = frozen.get(run_id, {}).get("best_epoch")
        parity = [x for x in deployment.get("parity", []) if x.get("run_id") == run_id]
        speeds = [x for x in deployment.get("benchmark", []) if x.get("run_id") == run_id]
        int8 = [x for x in export_report.get("int8", []) if x.get("run_id") == run_id]
        artifact_sizes = {x["runtime"]: x.get("size_bytes") for x in export_report.get("exports", []) if x.get("run_id") == run_id and x.get("status") == "EXPORTED"}
        host_rss = {x["runtime"]: x.get("rss_peak_bytes") for x in speeds}
        records.append({"run_id": run_id, "model_id": model_id, "imgsz": imgsz, "model_characteristics": model_characteristics(checkpoint_path(run_id), imgsz), "frozen_validation": {"mAP50": validation.get("metrics/mAP50(B)", {}).get("best"), "mAP50_95": validation.get("metrics/mAP50-95(B)", {}).get("best"), "precision": validation.get("metrics/precision(B)", {}).get("best"), "recall": validation.get("metrics/recall(B)", {}).get("best"), "best_epoch": best_epoch}, "checkpoint_sha256": EXPECTED_BEST[run_id], "export_size_bytes": artifact_sizes, "parity": {x["runtime"]: x["status"] for x in parity}, "host_reference_fps": {x["runtime"]: x["fps_mean"] for x in speeds}, "host_peak_rss_bytes": host_rss, "pi5_status": "BLOCKED_NO_RASPBERRY_PI_5_IN_WORKSPACE", "int8_status": {x["runtime"]: x["status"] for x in int8}, "selection_status": "PARETO_CANDIDATE_PENDING_RESEARCH_DESIGN"})
    result = {"status": "COMPLETE_WITH_PI_BLOCKED", "test_locked": True, "accuracy_selection_from_test": False, "records": records, "policy": ["frozen Scope18 validation mAP50/mAP50-95/precision/recall", "recall and mAP50-95 retained", "export/parity", "host runtime reference only; Pi5 not measured", "RAM/model size", "honest INT8 status"], "selection_decision": "NO_MODEL_FROZEN_WITHOUT_PI5_EVIDENCE"}
    write_json(RUNTIME / "model_selection_table.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("audit", "export", "benchmark", "all"), default="all")
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    audit = audit_inputs()
    if args.phase == "audit":
        print(json.dumps(audit, indent=2, ensure_ascii=False)); return 0 if audit["status"] == "PASS" else 2
    export_report = json.loads((RUNTIME / "export_report.json").read_text()) if args.phase == "benchmark" and (RUNTIME / "export_report.json").exists() else export_all(audit)
    if args.phase == "export":
        print(json.dumps(export_report, indent=2, ensure_ascii=False)); return 0 if export_report["status"] in {"PASS", "PARTIALLY_COMPLETE"} else 2
    deployment = parity_and_benchmark(audit, export_report)
    table = selection_table(audit, export_report, deployment)
    print(json.dumps({"audit": audit["status"], "exports": export_report["status"], "deployment": deployment["status"], "selection": table["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
