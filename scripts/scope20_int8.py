"""Scope 20 train-only INT8 calibration and isolated conversion investigation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope20"
SCOPE19 = ROOT / ".runtime/scope19"
EXPORTS19 = ROOT / "artifacts/exports/scope19"
EXPORTS20 = ROOT / "artifacts/exports/scope20"
ORDER = [("yolov8n", 640), ("yolov8n", 480), ("yolov11n", 640), ("yolov11n", 480), ("yolo26n", 640), ("yolo26n", 480)]


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


def calibration() -> dict:
    import cv2
    from ultralytics.data.augment import LetterBox

    manifest = json.loads((SCOPE19 / "calibration_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("source_split") != "train" or manifest.get("test_accessed") is not False or manifest.get("count") != 128:
        raise RuntimeError("Scope 19 calibration manifest is not the locked 128-image train-only manifest")
    records = []
    for model_id, size in ORDER:
        array_rows = []
        for path_string in manifest["paths"]:
            path = Path(path_string)
            image = cv2.imread(str(path))
            if image is None:
                raise FileNotFoundError(path)
            image = LetterBox(new_shape=(size, size), auto=False, stride=32)(image=image)
            image = image[..., ::-1].transpose(2, 0, 1).copy().astype(np.float32) / 255.0
            array_rows.append(image)
        array = np.stack(array_rows, axis=0)
        run_id = f"scope18-{model_id}-{size}"
        destination = RUNTIME / "calibration" / f"{run_id}.npy"
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.save(destination, array)
        records.append({"run_id": run_id, "path": str(destination), "sha256": sha256(destination), "sample_count": len(manifest["paths"]), "source_split": "train", "sample_ids": [Path(item).name for item in manifest["paths"]], "shape": list(array.shape), "dtype": str(array.dtype), "min": float(array.min()), "max": float(array.max()), "mean": float(array.mean()), "membership_source": str(SCOPE19 / "calibration_manifest.json")})
    result = {"status": "PASS", "records": records, "test_accessed": False, "policy": "same 128 locked train samples; representation-only NCHW float32 transform; no VAL/TEST"}
    write_json(RUNTIME / "int8_calibration.json", result)
    return result


def versions() -> dict:
    packages = {}
    for package in ("torch", "ultralytics", "tensorflow-cpu", "ai-edge-litert", "ai-edge-quantizer", "litert-torch", "onnx", "onnxruntime", "onnx2tf", "ncnn"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    return {"python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(), "packages": packages}


def convert(run_id: str, quantized: bool, tflite_backend: str = "flatbuffer_direct") -> dict:
    calibration_records = json.loads((RUNTIME / "int8_calibration.json").read_text(encoding="utf-8"))["records"]
    row = next(item for item in calibration_records if item["run_id"] == run_id)
    source_onnx = EXPORTS19 / run_id / "float32/onnx/model.onnx"
    onnx_path = RUNTIME / "onnx_inputs" / f"{run_id}.onnx"
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_onnx, onnx_path)
    converter_input_sha256_before = sha256(onnx_path)
    output = EXPORTS20 / run_id / (("int8_onnx2tf" if tflite_backend == "flatbuffer_direct" else "int8_onnx2tf_tfconverter") if quantized else ("float32_onnx2tf" if tflite_backend == "flatbuffer_direct" else "float32_onnx2tf_tfconverter"))
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "onnx2tf", "-i", str(onnx_path), "-o", str(output), "-coion", "-n", "-tb", tflite_backend]
    if quantized:
        # Calibration arrays are already float32 in [0, 1]; explicit mean/std
        # makes the onnx2tf full-integer contract unambiguous.
        command += ["-oiqt", "-cind", "images", row["path"], "0", "1"]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
    all_artifacts = [str(path) for path in output.rglob("*") if path.is_file()]
    artifacts = [path for path in all_artifacts if not quantized or any(token in Path(path).name.lower() for token in ("int8", "integer_quant"))]
    result = {"run_id": run_id, "quantized": quantized, "source_scope19_onnx": str(source_onnx), "source_scope19_onnx_sha256": sha256(source_onnx), "converter_input_copy": str(onnx_path), "converter_input_copy_sha256_before": converter_input_sha256_before, "converter_input_copy_sha256_after": sha256(onnx_path), "converter_mutated_copy": converter_input_sha256_before != sha256(onnx_path), "command": command, "returncode": completed.returncode, "status": "EXPORTED" if completed.returncode == 0 and artifacts else "BLOCKED", "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:], "artifacts": [{"path": path, "sha256": sha256(Path(path)), "size_bytes": Path(path).stat().st_size} for path in artifacts], "calibration": row if quantized else None, "environment": versions(), "test_accessed": False}
    write_json(RUNTIME / f"int8_conversion_{run_id}_{'int8' if quantized else 'float32'}.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("prepare", "convert"), required=True)
    parser.add_argument("--run-id", default="scope18-yolov8n-480")
    parser.add_argument("--quantized", action="store_true")
    parser.add_argument("--tflite-backend", choices=("flatbuffer_direct", "tf_converter"), default="flatbuffer_direct")
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if args.phase == "prepare":
        print(json.dumps(calibration(), indent=2, ensure_ascii=False)); return 0
    if not (RUNTIME / "int8_calibration.json").exists():
        calibration()
    result = convert(args.run_id, args.quantized, args.tflite_backend)
    print(json.dumps({"run_id": args.run_id, "quantized": args.quantized, "status": result["status"], "returncode": result["returncode"]}, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "EXPORTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
