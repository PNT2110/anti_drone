#!/usr/bin/env python3
"""Export the locked Phase 3 winner and produce a runtime-parity report."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import onnx
from onnx import TensorProto, helper
from ultralytics import YOLO


MODEL_RUNS = {
    "yolov8n": Path("artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2"),
    "yolov11n": Path("artifacts/experiments/drone-single-class/yolov11n/baseline-640-s42-drop01"),
    "yolo26n": Path("artifacts/experiments/drone-single-class/yolo26n/baseline-640-s42-drop01"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    else:
        for item in sorted(path.rglob("*")):
            if item.is_file():
                digest.update(str(item.relative_to(path)).encode())
                with item.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "not-a-git-worktree"


def normalized_onnx(source: Path, destination: Path, imgsz: int) -> Path:
    """Create the legacy TFLite contract: xywh normalized to [0, 1]."""
    graph = onnx.load(str(source))
    original = graph.graph.output[0]
    source_name = original.name
    box_name, score_name = "tflite_box_slice", "tflite_score_slice"
    normalized_name = "tflite_normalized_output"
    graph.graph.initializer.extend(
        [
            helper.make_tensor("tflite_slice_start0", TensorProto.INT64, [1], [0]),
            helper.make_tensor("tflite_slice_end0", TensorProto.INT64, [1], [4]),
            helper.make_tensor("tflite_slice_start4", TensorProto.INT64, [1], [4]),
            helper.make_tensor("tflite_slice_end4", TensorProto.INT64, [1], [5]),
            helper.make_tensor("tflite_slice_axis1", TensorProto.INT64, [1], [1]),
            helper.make_tensor("tflite_slice_step1", TensorProto.INT64, [1], [1]),
        ]
    )
    graph.graph.node.extend(
        [
            helper.make_node("Slice", [source_name, "tflite_slice_start0", "tflite_slice_end0", "tflite_slice_axis1", "tflite_slice_step1"], [box_name]),
            helper.make_node("Slice", [source_name, "tflite_slice_start4", "tflite_slice_end4", "tflite_slice_axis1", "tflite_slice_step1"], [score_name]),
            helper.make_node("Div", [box_name, "tflite_imgsz"], ["tflite_normalized_box"]),
            helper.make_node("Concat", ["tflite_normalized_box", score_name], [normalized_name], axis=1),
        ]
    )
    graph.graph.initializer.append(helper.make_tensor("tflite_imgsz", TensorProto.FLOAT, [1], [float(imgsz)]))
    graph.graph.output[0].name = normalized_name
    onnx.checker.check_model(graph)
    onnx.save(graph, str(destination))
    return destination


def representative_set(dataset_root: Path, output: Path, count: int) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    images = sorted((dataset_root / "images" / "test").glob("*.jpg"))[:count]
    if not images:
        raise FileNotFoundError("No test images for parity set")
    copied = []
    for image in images:
        target = output / image.name
        if not target.exists():
            shutil.copy2(image, target)
        copied.append(target)
    return copied


def export_profile(checkpoint: Path, runtime: str, target: Path, imgsz: int) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(checkpoint))
    if runtime == "tflite":
        # Ultralytics' current LiteRT exporter is coupled to a newer Torch
        # than the training environment.  Convert the already validated ONNX
        # graph with onnx2tf instead of silently changing the checkpoint.
        onnx_result = model.export(format="onnx", imgsz=imgsz, batch=1, dynamic=False, simplify=True, opset=12, nms=False, device="cpu")
        converter = Path(sys.executable).parent / "onnx2tf"
        if not converter.exists():
            raise FileNotFoundError(converter)
        temp_dir = Path(tempfile.mkdtemp(prefix="anti-drone-tflite-"))
        try:
            normalized_graph = temp_dir / "normalized.onnx"
            normalized_onnx(Path(str(onnx_result)), normalized_graph, imgsz)
            environment = dict(__import__("os").environ)
            environment["PATH"] = f"{Path(sys.executable).parent}:{environment.get('PATH', '')}"
            subprocess.run([str(converter), "-i", str(normalized_graph), "-o", str(temp_dir / "converted"), "-tb", "flatbuffer_direct", "-coion"], check=True, env=environment)
            candidates = sorted((temp_dir / "converted").glob("*_float32.tflite")) or sorted((temp_dir / "converted").glob("*.tflite"))
            if not candidates:
                raise FileNotFoundError("onnx2tf did not produce a .tflite file")
            destination = target / "model_float32.tflite"
            shutil.copy2(candidates[0], destination)
            return destination
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    export_args = {
        "format": runtime,
        "imgsz": imgsz,
        "batch": 1,
        "dynamic": False,
        "simplify": True,
        "nms": False,
        "device": "cpu",
    }
    if runtime == "onnx":
        export_args["opset"] = 12
    result = model.export(**export_args)
    source = Path(str(result))
    if not source.exists():
        raise FileNotFoundError(f"Exporter returned missing path: {source}")
    if runtime == "onnx":
        destination = target / source.name
        shutil.copy2(source, destination)
    elif runtime == "ncnn":
        destination = target / "best_ncnn_model"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
    else:
        destination = target / source.name
        if source.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    return destination


def prediction_signature(model_path: Path, images: list[Path], confidence: float) -> list[list[float]]:
    model = YOLO(str(model_path))
    signature: list[list[float]] = []
    for image in images:
        result = model.predict(source=str(image), imgsz=640, conf=confidence, iou=0.70, device="cpu", verbose=False)[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            continue
        xyxy = boxes.xyxy.cpu().numpy()
        conf = boxes.conf.cpu().numpy()
        cls = boxes.cls.cpu().numpy()
        for box, score, class_id in zip(xyxy, conf, cls):
            signature.append([float(image.name.__hash__() % 1000000), float(class_id), float(score), *map(float, box)])
    signature.sort(key=lambda row: (row[0], -row[2]))
    return signature


def parity(checkpoint: Path, profiles: dict[str, Path], images: list[Path], confidence: float) -> dict:
    result = {"status": "DONE", "profiles": {}, "tolerance": {"max_abs_confidence": 0.05, "max_abs_box_pixels": 5.0, "class_exact": True}, "images": [str(item) for item in images]}
    reference = prediction_signature(checkpoint, images, confidence)
    for runtime, model_path in profiles.items():
        started = time.time()
        item = {"model": str(model_path), "status": "DONE", "started_at": started}
        try:
            candidate = prediction_signature(model_path, images, confidence)
            item["reference_detections"] = len(reference)
            item["candidate_detections"] = len(candidate)
            item["class_exact"] = [row[1] for row in candidate] == [row[1] for row in reference]
            pairs = list(zip(reference, candidate))
            confidence_differences = [abs(left[2] - right[2]) for left, right in pairs]
            box_differences = [max(abs(left[index] - right[index]) for index in range(3, 7)) for left, right in pairs]
            item["paired_detections"] = len(pairs)
            item["max_abs_confidence"] = max(confidence_differences, default=0.0)
            item["max_abs_box_pixels"] = max(box_differences, default=0.0)
            if not item["class_exact"] or len(reference) != len(candidate) or item["max_abs_confidence"] > 0.05 or item["max_abs_box_pixels"] > 5.0:
                item["status"] = "BLOCKED"
                result["status"] = "BLOCKED"
        except Exception as exc:
            item["status"] = "BLOCKED"
            item["error"] = f"{type(exc).__name__}: {exc}"
            result["status"] = "BLOCKED"
        item["elapsed_seconds"] = time.time() - started
        result["profiles"][runtime] = item
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="yolov8n", choices=sorted(MODEL_RUNS))
    parser.add_argument("--dataset-root", type=Path, default=Path("data/processed/drone-single-class"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/deploy"))
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--parity-images", type=int, default=8)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--skip-export", action="store_true")
    args = parser.parse_args()
    args.dataset_root = args.dataset_root.resolve()
    args.output_root = args.output_root.resolve() / args.model_id
    checkpoint = (MODEL_RUNS[args.model_id] / "weights/best.pt").resolve()
    if not checkpoint.exists():
        raise FileNotFoundError(checkpoint)
    args.output_root.mkdir(parents=True, exist_ok=True)
    images = representative_set(args.dataset_root, Path(".runtime/parity-set"), args.parity_images)
    profiles: dict[str, Path] = {}
    errors: dict[str, str] = {}
    for runtime in ("onnx", "ncnn", "tflite"):
        target = args.output_root / runtime
        try:
            profiles[runtime] = export_profile(checkpoint, runtime, target, args.imgsz) if not args.skip_export else next(target.iterdir())
        except Exception as exc:
            errors[runtime] = f"{type(exc).__name__}: {exc}"
            (target / "EXPORT_BLOCKED.txt").parent.mkdir(parents=True, exist_ok=True)
            (target / "EXPORT_BLOCKED.txt").write_text(errors[runtime] + "\n", encoding="utf-8")
    parity_result = parity(checkpoint, profiles, images, args.confidence) if profiles else {"status": "BLOCKED", "profiles": {}}
    for runtime, error in errors.items():
        parity_result.setdefault("profiles", {})[runtime] = {"status": "BLOCKED", "error": error}
    if errors:
        parity_result["status"] = "BLOCKED"
    metadata = {
        "status": parity_result["status"],
        "model_id": args.model_id,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "input": {"width": args.imgsz, "height": args.imgsz, "layout": "NCHW", "dtype": "float32", "color": "RGB", "normalization": "pixel / 255.0", "letterbox": True},
        "class_map": {"0": "drone"},
        "threshold": {"confidence": args.confidence, "nms_iou": 0.70},
        "profiles": {key: {"path": str(value), "sha256": sha256(value)} for key, value in profiles.items()},
        "exporter": {"ultralytics": __import__("ultralytics").__version__, "python": platform.python_version(), "git": git_head(), "timestamp_unix": time.time()},
        "representative_set": {"path": str(Path(".runtime/parity-set").resolve()), "count": len(images), "sha256": sha256(Path(".runtime/parity-set"))},
    }
    (args.output_root / "parity.json").write_text(json.dumps(parity_result, indent=2), encoding="utf-8")
    (args.output_root / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    sums = []
    for item in sorted(args.output_root.rglob("*")):
        if item.is_file() and item.name not in {"SHA256SUMS", "metadata.json"}:
            sums.append(f"{sha256(item)}  {item.relative_to(args.output_root)}")
    (args.output_root / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"status": metadata["status"], "profiles": list(profiles), "errors": errors}, indent=2))
    raise SystemExit(0 if metadata["status"] == "DONE" else 2)


if __name__ == "__main__":
    main()
