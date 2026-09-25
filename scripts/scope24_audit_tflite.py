#!/usr/bin/env python3
"""Record Scope 24 TFLite artifact metadata and runtime load status."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from ai_edge_litert.interpreter import Interpreter, OpResolverType

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "scope24"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def detail(d):
    q = d["quantization_parameters"]
    return {"name": d["name"], "shape": d["shape"].tolist(), "dtype": np.dtype(d["dtype"]).name, "quantization": [float(d["quantization"][0]), int(d["quantization"][1])], "scales": np.asarray(q["scales"]).astype(float).tolist(), "zero_points": np.asarray(q["zero_points"]).astype(int).tolist(), "quantized_dimension": int(q["quantized_dimension"])}


def main():
    rows = []
    for run_id, size in (("scope18-yolov8n-480", 480), ("scope18-yolov8n-640", 640)):
        for variant in ("T1", "T2"):
            path = ROOT / "artifacts/exports/scope24" / run_id / variant / "model_full_integer_quant.tflite"
            row = {"run_id": run_id, "size": size, "variant": variant, "path": str(path), "status": "MISSING"}
            if path.exists():
                row.update({"sha256": sha256(path), "bytes": path.stat().st_size})
                try:
                    it = Interpreter(model_path=str(path), experimental_op_resolver_type=OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES)
                    it.allocate_tensors()
                    inputs, outputs = it.get_input_details(), it.get_output_details()
                    ops = sorted({x["op_name"] for x in it._get_ops_details()})
                    status = "FULL_INTEGER_INT8" if inputs[0]["dtype"] in (np.int8, np.uint8) and outputs[0]["dtype"] in (np.int8, np.uint8) and "CONV_2D" in ops else "HYBRID_OR_INVALID"
                    probe = np.load(Path("/home/pnt/.cache/antidrone_scope24_calibration") / f"{run_id}.npy")[0:1]
                    scale, zero = inputs[0]["quantization"]
                    qprobe = np.rint(probe / scale + zero).clip(np.iinfo(inputs[0]["dtype"]).min, np.iinfo(inputs[0]["dtype"]).max).astype(inputs[0]["dtype"])
                    it.set_tensor(inputs[0]["index"], qprobe)
                    try:
                        it.invoke()
                        invoke_status = "PASS"
                    except Exception as invoke_exc:
                        invoke_status = "BLOCKED"
                        status = "RUNTIME_INVOKE_BLOCKED"
                        row["invoke_error"] = repr(invoke_exc)
                    row.update({"status": status, "invoke_status": invoke_status, "input": detail(inputs[0]), "output": detail(outputs[0]), "ops": ops, "default_delegates_disabled": True})
                except Exception as exc:
                    row.update({"status": "RUNTIME_LOAD_BLOCKED", "error": repr(exc)})
            rows.append(row)
    result = {"test_accessed": False, "rows": rows}
    (RUNTIME / "tflite_artifact_audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
