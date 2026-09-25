#!/usr/bin/env python3
"""Run one frozen Scope 23 PTQ configuration and evaluate it on host."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope21_pi_runner import decode, iou, load_runtime, preprocess  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope23"
SCOPE19 = ROOT / ".runtime/scope19"
TOOLS = ROOT / ".runtime/scope22/toolchain/ncnn-build/tools/quantize"
APPROVED = [("scope18-yolov8n-480", 480), ("scope18-yolov8n-640", 640), ("scope18-yolov11n-480", 480)]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def command(cmd: list[str], log: Path) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    log.write_text("$ " + " ".join(cmd) + "\n\nSTDOUT\n" + p.stdout + "\nSTDERR\n" + p.stderr)
    return {"command": cmd, "returncode": p.returncode, "stdout_tail": p.stdout[-2000:], "stderr_tail": p.stderr[-6000:]}


def ncnn_once(net, image: np.ndarray, size: int) -> tuple[list[dict], dict]:
    import ncnn
    tensor, gain, pad = preprocess(image, size)
    rgb_u8 = np.ascontiguousarray(np.clip(tensor[0].transpose(1, 2, 0) * 255.0, 0, 255).astype(np.uint8))
    mat = ncnn.Mat.from_pixels(rgb_u8, ncnn.Mat.PixelType.PIXEL_RGB, size, size)
    mat.substract_mean_normalize(np.zeros(3, dtype=np.float32), np.ones(3, dtype=np.float32) / 255.0)
    ex = net.create_extractor(); ex.input("in0", mat); ret, out = ex.extract("out0")
    if ret != 0:
        raise RuntimeError(f"NCNN extract failed: {ret}")
    raw = np.asarray(out)[None, ...]
    if raw.shape[1] == 5:
        before_nms = int(np.sum(raw[0, 4, :] >= 0.25))
    else:
        before_nms = int(np.sum(raw[0, :, 4] >= 0.25))
    detections, contract = decode(raw, gain, pad, image.shape[:2])
    contract["pre_nms_count_at_conf_0.25"] = before_nms
    contract["post_nms_count"] = len(detections)
    return detections, contract


def gate(reference: list[dict], candidate: list[dict]) -> dict:
    result = {"reference_count": len(reference), "candidate_count": len(candidate), "confidence_abs": 0.0, "bbox_iou": 1.0, "class_exact": True}
    if len(reference) != len(candidate):
        result["count_mismatch"] = True
    else:
        result["count_mismatch"] = False
    for left, right in zip(reference, candidate):
        result["confidence_abs"] = max(result["confidence_abs"], abs(left["confidence"] - right["confidence"]))
        result["bbox_iou"] = min(result["bbox_iou"], iou(left["bbox"], right["bbox"]))
        result["class_exact"] = result["class_exact"] and left["class"] == right["class"]
    result["status"] = "PASS" if not result["count_mismatch"] and result["class_exact"] and result["bbox_iou"] >= 0.90 and result["confidence_abs"] <= 0.20 else "FAIL"
    return result


def make_export(exp_id: str, run_id: str, size: int, method: str, count: int) -> dict:
    src = ROOT / "artifacts/exports/scope19" / run_id / "float32/ncnn/model_ncnn_model"
    work = RUNTIME / "experiments" / exp_id / run_id; work.mkdir(parents=True, exist_ok=True)
    out = ROOT / "artifacts/exports/scope23" / run_id / exp_id / "ncnn"; out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((RUNTIME / "calibration_manifests" / f"{run_id}_{count}.json").read_text())
    list_path = work / "npy_list.txt"; list_path.write_text("\n".join(manifest["npy_paths"]) + "\n")
    table = work / "calibration.table"
    table_cmd = [str(TOOLS / "ncnn2table"), str(src / "model.ncnn.param"), str(src / "model.ncnn.bin"), str(list_path), str(table), f"shape=[{size},{size},3]", f"method={method}", "type=1", "thread=4"]
    table_run = command(table_cmd, work / "ncnn2table.log")
    row = {"experiment_id": exp_id, "run_id": run_id, "size": size, "method": method, "calibration_count": count, "calibration_manifest": str(RUNTIME / "calibration_manifests" / f"{run_id}_{count}.json"), "npy_list": str(list_path), "table": str(table), "ncnn2table": table_run, "status": "EXPORT_FAIL"}
    if table_run["returncode"] != 0 or not table.is_file():
        return row
    out_param, out_bin = out / "model.ncnn.param", out / "model.ncnn.bin"
    int8_cmd = [str(TOOLS / "ncnn2int8"), str(src / "model.ncnn.param"), str(src / "model.ncnn.bin"), str(out_param), str(out_bin), str(table)]
    int8_run = command(int8_cmd, work / "ncnn2int8.log")
    row["ncnn2int8"] = int8_run
    if int8_run["returncode"] == 0 and out_param.is_file() and out_bin.is_file():
        text = out_param.read_text(errors="replace")
        markers = text.count("8=2") + text.count("8=1")
        row["artifact"] = {"param": str(out_param), "bin": str(out_bin), "param_sha256": sha256(out_param), "bin_sha256": sha256(out_bin), "param_bytes": out_param.stat().st_size, "bin_bytes": out_bin.stat().st_size, "int8_markers": markers}
        row["status"] = "HOST_RUNTIME_PENDING"
    return row


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--experiment", choices=("E1", "E2", "E3"), required=True)
    args = parser.parse_args()
    plan = json.loads((RUNTIME / "experiment_plan.json").read_text())
    spec = next(x for x in plan["experiments"] if x["id"] == args.experiment)
    ids = [("scope18-yolov8n-480", 480), ("scope18-yolov8n-640", 640)]
    exports = [make_export(args.experiment, run_id, size, spec["method"], spec["calibration_count"]) for run_id, size in ids]
    export_by_id = {x["run_id"]: x for x in exports}
    fixed = json.loads((SCOPE19 / "benchmark_input_manifest.json")).get("paths", []) if False else json.loads((SCOPE19 / "benchmark_input_manifest.json").read_text())["paths"]
    secondary = json.loads((RUNTIME / "secondary_diagnostic_manifest.json").read_text())["paths"]
    sets = {"fixed_8": fixed, "secondary_32": secondary}
    results = []
    for run_id, size in ids:
        row = export_by_id[run_id]
        if row["status"] != "HOST_RUNTIME_PENDING":
            results.append({"run_id": run_id, "status": "INT8_EXPORT_FAIL", "export": row}); continue
        fp_root = ROOT / "artifacts/exports/scope19" / run_id / "float32/ncnn/model_ncnn_model"
        int_root = Path(row["artifact"]["param"]).parent
        fp = {"backend": "ncnn", "artifact_path": str(fp_root), "threads": 4}; it = {"backend": "ncnn", "artifact_path": str(int_root), "threads": 4}
        fp_net, _ = load_runtime(fp); int_net, _ = load_runtime(it)
        set_results = {}
        for set_name, paths in sets.items():
            image_rows = []
            for path in paths:
                image = cv2.imread(path)
                fp_det, fp_contract = ncnn_once(fp_net, image, size)
                int_det, int_contract = ncnn_once(int_net, image, size)
                image_rows.append({"image": Path(path).name, "fp32_detections": fp_det, "int8_detections": int_det, "fp32_contract": fp_contract, "int8_contract": int_contract, "gate": gate(fp_det, int_det)})
            set_results[set_name] = {"count": len(image_rows), "rows": image_rows, "count_mismatch": sum(x["gate"]["count_mismatch"] for x in image_rows), "class_mismatch": sum(not x["gate"]["class_exact"] for x in image_rows), "minimum_bbox_iou": min(x["gate"]["bbox_iou"] for x in image_rows), "maximum_confidence_abs": max(x["gate"]["confidence_abs"] for x in image_rows), "status": "PASS" if all(x["gate"]["status"] == "PASS" for x in image_rows) else "FAIL"}
        results.append({"run_id": run_id, "experiment_id": args.experiment, "size": size, "status": "HOST_INT8_PARITY_PASS" if all(x["status"] == "PASS" for x in set_results.values()) else "HOST_INT8_PARITY_FAIL", "export": row, "sets": set_results})
    result = {"experiment_id": args.experiment, "status": "PASS" if all(x["status"] == "HOST_INT8_PARITY_PASS" for x in results) else "FAIL", "acceptance": plan["primary_acceptance"], "results": results, "thresholds": {"confidence": 0.25, "nms_iou": 0.70}, "test_accessed": False}
    out = RUNTIME / "experiments" / args.experiment / "host_results.json"; out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"experiment": args.experiment, "status": result["status"], "candidates": [(x["run_id"], x["status"], {k: v["status"] for k, v in x.get("sets", {}).items()}) for x in results]}, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
