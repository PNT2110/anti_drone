"""Scope 20 parity root-cause and corrected train-only parity harness.

The harness deliberately uses one static preprocessing contract for PT, ONNX and
NCNN. It never reads the V3 test split and never modifies checkpoints or Scope 19
exports.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope20"
SCOPE19 = ROOT / ".runtime/scope19"
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
SCOPE19_EXPORTS = ROOT / "artifacts/exports/scope19"
ORDER = [("yolov8n", 640), ("yolov8n", 480), ("yolov11n", 640), ("yolov11n", 480), ("yolo26n", 640), ("yolo26n", 480)]
EXPECTED_BEST = {
    "scope18-yolov8n-640": "debcef45f0a1667f16c62daf7a8f42d0e5932be498b549b2f985bc72915e9718",
    "scope18-yolov8n-480": "359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e",
    "scope18-yolov11n-640": "ab2d146424a2c9c0ce053b122463d7d2e796834e9671a60bdeacd4047ca68186",
    "scope18-yolov11n-480": "6f086a2206a466c1037e6aab3ddbbf1afc40b38f7643e9be4f83a85630a81e05",
    "scope18-yolo26n-640": "3153d0ffdd6b4db7b3fd28fa4026636fe3ffad19acaedbea1c4f35c996fb8bae",
    "scope18-yolo26n-480": "1500fb46bbf01910f85a0b75b37e00f275bf0cb725c0829e7c2db293ea6a23d6",
}
PARITY_GATE = {"confidence_abs": 0.05, "bbox_iou_min": 0.95, "class_exact": True, "detection_count_exact": True}
RAW_DIAGNOSTIC = {"abs_atol": 1e-4, "rel_rtol": 1e-4}


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


def load(name: str) -> dict:
    return json.loads((SCOPE19 / name).read_text(encoding="utf-8"))


def checkpoint_path(run_id: str) -> Path:
    return ROOT / "artifacts/experiments/scope18-v3-labelrepair" / run_id / "attempt-batch16/weights/best.pt"


def export_path(run_id: str, runtime: str) -> Path:
    if runtime == "onnx":
        return SCOPE19_EXPORTS / run_id / "float32/onnx/model.onnx"
    if runtime == "ncnn":
        return SCOPE19_EXPORTS / run_id / "float32/ncnn/model_ncnn_model"
    raise ValueError(runtime)


def input_audit() -> dict:
    errors: list[str] = []
    previous = load("input_audit.json")
    if previous.get("status") != "PASS" or previous.get("test_accessed") is not False:
        errors.append("Scope 19 input audit is not PASS/test_locked")
    expected_dataset = {
        "manifest": "bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45",
        "split_registry": "c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1",
    }
    actual_dataset = {"manifest": sha256(DATASET / "manifest.json"), "split_registry": sha256(DATASET / "split_registry.json")}
    if actual_dataset != expected_dataset:
        errors.append(f"dataset checksum changed: {actual_dataset}")
    checkpoints = {}
    for model_id, imgsz in ORDER:
        run_id = f"scope18-{model_id}-{imgsz}"
        path = checkpoint_path(run_id)
        actual = sha256(path) if path.is_file() else None
        checkpoints[run_id] = {"path": str(path), "actual": actual, "expected": EXPECTED_BEST[run_id], "match": actual == EXPECTED_BEST[run_id]}
        if actual != EXPECTED_BEST[run_id]:
            errors.append(f"best.pt changed: {run_id}")
    benchmark = load("benchmark_input_manifest.json")
    calibration = load("calibration_manifest.json")
    if benchmark.get("split") != "train" or benchmark.get("test_accessed") is not False or len(benchmark.get("paths", [])) != 8:
        errors.append("Scope 19 benchmark manifest is not the locked 8-image train subset")
    if calibration.get("source_split") != "train" or calibration.get("test_accessed") is not False or calibration.get("count") != 128:
        errors.append("Scope 19 calibration manifest is not the locked 128-image train subset")
    export_hashes = {}
    export_report = load("export_report.json")
    for item in export_report.get("exports", []):
        if item.get("runtime") not in {"onnx", "ncnn"} or item.get("status") != "EXPORTED":
            continue
        path = export_path(item["run_id"], item["runtime"])
        actual = sha256(path) if path.exists() else None
        export_hashes[f"{item['run_id']}:{item['runtime']}"] = {"path": str(path), "actual": actual, "expected": item.get("sha256"), "match": actual == item.get("sha256")}
        if actual != item.get("sha256"):
            errors.append(f"Scope 19 export changed: {item['run_id']} {item['runtime']}")
    versions = {}
    for package in ("torch", "ultralytics", "tensorflow-cpu", "ai-edge-litert", "ai-edge-quantizer", "litert-torch", "onnx", "onnxruntime", "onnx2tf", "ncnn"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    result = {
        "status": "PASS" if not errors else "BLOCKED_INPUT_CHANGED",
        "errors": errors,
        "dataset": actual_dataset,
        "checkpoints": checkpoints,
        "scope19_export_hashes": export_hashes,
        "benchmark_manifest": str(SCOPE19 / "benchmark_input_manifest.json"),
        "calibration_manifest": str(SCOPE19 / "calibration_manifest.json"),
        "test_accessed": False,
        "test_policy": "locked; no test inference or test accuracy",
        "environment_before": {"python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(), "packages": versions},
    }
    write_json(RUNTIME / "input_audit.json", result)
    write_json(RUNTIME / "environment_before.json", result["environment_before"])
    return result


def stats(array: np.ndarray | object) -> dict:
    values = np.asarray(array)
    return {"shape": list(values.shape), "dtype": str(values.dtype), "min": float(values.min()), "max": float(values.max()), "mean": float(values.mean()), "sha256": hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()}


def tensor_from_output(output):
    import torch

    if isinstance(output, torch.Tensor):
        return output
    if isinstance(output, (list, tuple)):
        for item in output:
            try:
                return tensor_from_output(item)
            except TypeError:
                continue
    raise TypeError(f"cannot find tensor in output {type(output)}")


def decoded_candidates(raw):
    import torch
    from ultralytics.utils import ops

    raw = raw.detach().float().cpu()
    if raw.ndim != 3:
        raise ValueError(f"unexpected raw rank: {tuple(raw.shape)}")
    if raw.shape[1] == 5:
        # Standard exported detect graph: xywh + one class score, no embedded NMS.
        candidates = raw[0].transpose(0, 1)
        boxes = ops.xywh2xyxy(candidates[:, :4])
        return torch.cat((boxes, candidates[:, 4:5], torch.zeros((candidates.shape[0], 1))), dim=1), {"xywh": True, "nms_embedded": False, "candidate_count": int(candidates.shape[0])}
    if raw.shape[2] == 6:
        # YOLO26 end-to-end export: xyxy + confidence + class, top-k/NMS embedded.
        return raw[0], {"xywh": False, "nms_embedded": True, "candidate_count": int(raw.shape[1])}
    raise ValueError(f"unknown output contract: {tuple(raw.shape)}")


def final_detections(raw, preprocess_shape, original_shape):
    import torch
    from ultralytics.utils import nms, ops

    raw = raw.detach().float().cpu()
    if raw.shape[1] == 5:
        pred = nms.non_max_suppression(raw, 0.25, 0.70, nc=1, end2end=False)[0]
    elif raw.shape[2] == 6:
        pred = raw[0]
        pred = pred[pred[:, 4] >= 0.25]
    else:
        raise ValueError(f"unknown output contract: {tuple(raw.shape)}")
    pred = pred.clone() if isinstance(pred, torch.Tensor) else torch.as_tensor(pred)
    if len(pred):
        ops.scale_boxes(preprocess_shape, pred[:, :4], original_shape)
    return [{"class": int(row[5]), "confidence": float(row[4]), "bbox": [float(x) for x in row[:4]]} for row in pred]


def iou(left, right):
    ax1, ay1, ax2, ay2 = left
    bx1, by1, bx2, by2 = right
    ix1, iy1, ix2, iy2 = max(ax1, bx1), max(ay1, by1), min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    aa = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    ab = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = aa + ab - inter
    return inter / union if union else (1.0 if aa == ab == 0 else 0.0)


def compare_final(reference: list[dict], candidate: list[dict]) -> dict:
    result = {"status": "PARITY_PASS", "reference_count": len(reference), "candidate_count": len(candidate), "max_confidence_abs": 0.0, "min_bbox_iou": 1.0, "class_exact": True}
    if len(reference) != len(candidate):
        result["status"] = "PARITY_FAIL"
    for left, right in zip(reference, candidate):
        result["max_confidence_abs"] = max(result["max_confidence_abs"], abs(left["confidence"] - right["confidence"]))
        result["min_bbox_iou"] = min(result["min_bbox_iou"], iou(left["bbox"], right["bbox"]))
        result["class_exact"] = result["class_exact"] and left["class"] == right["class"]
    if result["max_confidence_abs"] > PARITY_GATE["confidence_abs"] or result["min_bbox_iou"] < PARITY_GATE["bbox_iou_min"] or not result["class_exact"]:
        result["status"] = "PARITY_FAIL"
    return result


def parity_trace(audit: dict) -> dict:
    import cv2
    from ultralytics.models.yolo.detect.predict import DetectionPredictor

    if audit["status"] != "PASS":
        result = {"status": "BLOCKED_INPUT_CHANGED"}
        write_json(RUNTIME / "parity_trace.json", result)
        return result
    manifests = load("benchmark_input_manifest.json")
    paths = [Path(item) for item in manifests["paths"]]
    records: list[dict] = []
    corrected: list[dict] = []
    legacy_preprocess: list[dict] = []
    for model_id, imgsz in ORDER:
        run_id = f"scope18-{model_id}-{imgsz}"
        paths_by_backend = {"pytorch": checkpoint_path(run_id), "onnx": export_path(run_id, "onnx"), "ncnn": export_path(run_id, "ncnn")}
        predictors = {}
        for backend, path in paths_by_backend.items():
            predictor = DetectionPredictor(overrides={"imgsz": imgsz, "conf": 0.25, "iou": 0.70, "device": "cpu", "verbose": False, "rect": False})
            predictor.setup_model(str(path), verbose=False)
            predictor.imgsz = (imgsz, imgsz)
            predictors[backend] = predictor
        for image_path in paths:
            image = cv2.imread(str(image_path))
            if image is None:
                raise FileNotFoundError(image_path)
            per_backend = {}
            for backend, predictor in predictors.items():
                pre = predictor.preprocess([image])
                raw = tensor_from_output(predictor.model(pre))
                raw_np = raw.detach().float().cpu().numpy()
                decoded, contract = decoded_candidates(raw)
                final = final_detections(raw, pre.shape[2:], image.shape)
                decoded_np = decoded.detach().cpu().numpy()
                per_backend[backend] = {"preprocess": stats(pre.detach().cpu().numpy()), "raw": stats(raw_np), "raw_array": raw_np, "raw_representative": raw_np.reshape(-1)[:12].tolist(), "decoded": stats(decoded_np), "decoded_array": decoded_np, "decoded_representative": decoded_np.reshape(-1, decoded_np.shape[-1])[:5].tolist(), "contract": contract, "final": final}
            ref = per_backend["pytorch"]
            for backend in ("onnx", "ncnn"):
                cand = per_backend[backend]
                pre_equal = ref["preprocess"]["sha256"] == cand["preprocess"]["sha256"]
                raw_shape_equal = ref["raw"]["shape"] == cand["raw"]["shape"]
                raw_diff = None
                if raw_shape_equal:
                    raw_diff = float(np.max(np.abs(ref["raw_array"] - cand["raw_array"])))
                decoded_shape_equal = ref["decoded"]["shape"] == cand["decoded"]["shape"]
                decoded_diff = None
                if decoded_shape_equal:
                    decoded_diff = float(np.max(np.abs(ref["decoded_array"] - cand["decoded_array"])))
                final_cmp = compare_final(ref["final"], cand["final"])
                first = "none"
                if not pre_equal:
                    first = "preprocess"
                elif not raw_shape_equal:
                    first = "output_contract"
                elif final_cmp["status"] != "PARITY_PASS" and raw_diff is not None and raw_diff > RAW_DIAGNOSTIC["abs_atol"]:
                    first = "raw_model_output"
                elif not decoded_shape_equal:
                    first = "decode"
                elif final_cmp["status"] != "PARITY_PASS" and decoded_diff is not None and decoded_diff > RAW_DIAGNOSTIC["abs_atol"]:
                    first = "decode"
                elif final_cmp["status"] != "PARITY_PASS":
                    first = "nms_or_coordinate_restore"
                record = {"run_id": run_id, "image": str(image_path), "backend": backend, "preprocess_equal": pre_equal, "pytorch_raw_shape": ref["raw"]["shape"], "backend_raw_shape": cand["raw"]["shape"], "raw_shape_equal": raw_shape_equal, "raw_max_abs_representative_diff": raw_diff, "pytorch_decoded_shape": ref["decoded"]["shape"], "backend_decoded_shape": cand["decoded"]["shape"], "decoded_shape_equal": decoded_shape_equal, "decoded_max_abs_representative_diff": decoded_diff, "final": final_cmp, "first_divergence": first, "pytorch_contract": ref["contract"], "backend_contract": cand["contract"]}
                records.append(record)
        # Reproduce the Scope 19 wrapper policy: rect=True for both calls. PT
        # then takes stride-minimal padding, while a static export is forced to
        # the square graph input. This is the causal preprocess mismatch.
        legacy_pt = DetectionPredictor(overrides={"imgsz": imgsz, "conf": 0.25, "iou": 0.70, "device": "cpu", "verbose": False, "rect": True})
        legacy_export = DetectionPredictor(overrides={"imgsz": imgsz, "conf": 0.25, "iou": 0.70, "device": "cpu", "verbose": False, "rect": True})
        legacy_pt.setup_model(str(checkpoint_path(run_id)), verbose=False)
        legacy_export.setup_model(str(export_path(run_id, "onnx")), verbose=False)
        legacy_pt.imgsz = (imgsz, imgsz)
        legacy_export.imgsz = (imgsz, imgsz)
        for image_path in paths:
            image = cv2.imread(str(image_path))
            pt_pre = legacy_pt.preprocess([image]).detach().cpu().numpy()
            export_pre = legacy_export.preprocess([image]).detach().cpu().numpy()
            legacy_preprocess.append({"run_id": run_id, "image": str(image_path), "pytorch_hash": stats(pt_pre)["sha256"], "static_export_hash": stats(export_pre)["sha256"], "equal": bool(np.array_equal(pt_pre, export_pre)), "pytorch_shape": list(pt_pre.shape), "static_export_shape": list(export_pre.shape), "pytorch_mean": float(pt_pre.mean()), "static_export_mean": float(export_pre.mean())})
        for backend in ("onnx", "ncnn"):
            rows = [r for r in records if r["run_id"] == run_id and r["backend"] == backend]
            status = "PARITY_PASS" if all(r["final"]["status"] == "PARITY_PASS" for r in rows) else "PARITY_FAIL"
            first_counts = {}
            for row in rows:
                first_counts[row["first_divergence"]] = first_counts.get(row["first_divergence"], 0) + 1
            corrected.append({"run_id": run_id, "backend": backend, "status": status, "image_count": len(rows), "first_divergence_counts": first_counts, "gate": PARITY_GATE})
    result = {"status": "PASS" if all(row["status"] == "PARITY_PASS" for row in corrected) else "PARTIALLY_COMPLETE", "preprocess_policy": {"color_input": "cv2 BGR then Ultralytics BGR-to-RGB", "conversion": "uint8 to float32 then /255", "resize": "letterbox", "auto": False, "padding": "constant 114", "interpolation": "Ultralytics LetterBox default", "tensor": "NCHW", "batch": 1, "static_size": "per run 480 or 640", "stride_alignment": "32 but auto padding disabled"}, "scope19_failure_reproduction": {"policy": "rect=True passed to both PT and static export wrappers", "records": legacy_preprocess, "mismatch_count": sum(not row["equal"] for row in legacy_preprocess), "total": len(legacy_preprocess), "cause": "PyTorch format permits stride-minimal auto padding; static ONNX/NCNN format forces square static input"}, "diagnostic_tolerance": RAW_DIAGNOSTIC, "acceptance_gate": PARITY_GATE, "records": records, "summary": corrected, "test_accessed": False, "corrected_harness": "rect=False is forced for PyTorch and static exports; no export or checkpoint is overwritten"}
    write_json(RUNTIME / "parity_trace.json", result)
    write_json(RUNTIME / "parity_summary.json", {"status": result["status"], "summary": corrected, "test_accessed": False, "acceptance_gate": PARITY_GATE})
    return result


def pi_audit() -> dict:
    def run(command: list[str]) -> str | None:
        try:
            return subprocess.run(command, capture_output=True, text=True, timeout=5, check=False).stdout.strip() or subprocess.run(command, capture_output=True, text=True, timeout=5, check=False).stderr.strip()
        except (OSError, subprocess.TimeoutExpired):
            return None
    result = {"status": "PI_BENCHMARK_BLOCKED", "identity": {"uname_a": run(["uname", "-a"]), "uname_m": run(["uname", "-m"]), "device_tree_model": (Path("/proc/device-tree/model").read_text(errors="replace").strip("\x00\n") if Path("/proc/device-tree/model").exists() else None), "rpicam_hello": run(["rpicam-hello", "--version"]), "vcgencmd_temp": run(["vcgencmd", "measure_temp"]), "vcgencmd_throttled": run(["vcgencmd", "get_throttled"])} , "reason": "No Raspberry Pi 5 identity or remote Pi access is available from this workspace; current host is x86_64.", "test_accessed": False}
    write_json(RUNTIME / "pi_input_audit.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("audit", "parity", "pi-audit", "all"), default="all")
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    audit = input_audit()
    if args.phase == "audit":
        print(json.dumps(audit, indent=2, ensure_ascii=False)); return 0 if audit["status"] == "PASS" else 2
    if args.phase in {"parity", "all"}:
        trace = parity_trace(audit)
    else:
        trace = None
    pi = pi_audit() if args.phase in {"pi-audit", "all"} else None
    print(json.dumps({"input": audit["status"], "parity": trace["status"] if trace else None, "pi": pi["status"] if pi else None}, indent=2, ensure_ascii=False))
    return 0 if audit["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
