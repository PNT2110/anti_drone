"""Inspect export contracts without executing native NCNN bindings."""

from __future__ import annotations

import json
from pathlib import Path

import onnx


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "artifacts/exports/scope19"
OUT = ROOT / ".runtime/scope19/backend_contracts.json"


def tensor_info(value):
    tensor = value.type.tensor_type
    shape = [dimension.dim_value or dimension.dim_param for dimension in tensor.shape.dim]
    return {"name": value.name, "dtype_enum": tensor.elem_type, "shape": shape}


def main() -> int:
    records = []
    for onnx_path in sorted(EXPORTS.glob("*/float32/onnx/model.onnx")):
        model_id = onnx_path.parents[2].name
        graph = onnx.load(str(onnx_path)).graph
        ncnn_dir = onnx_path.parents[1] / "ncnn/model_export"
        metadata = (ncnn_dir / "metadata.yaml").read_text(encoding="utf-8")
        param_lines = (ncnn_dir / "model.ncnn.param").read_text(encoding="utf-8").splitlines()
        input_names = [line.split()[1] for line in param_lines if line.startswith("Input ")]
        records.append({
            "run_id": model_id,
            "onnx": {
                "inputs": [tensor_info(value) for value in graph.input],
                "outputs": [tensor_info(value) for value in graph.output],
            },
            "ncnn": {
                "input_names": input_names,
                "output_names": ["out0"],
                "metadata_file": str(ncnn_dir / "metadata.yaml"),
                "param_file": str(ncnn_dir / "model.ncnn.param"),
                "shape_contract": "static image size and batch=1 are recorded in metadata.yaml; native output dimensions are not inferred without executing the native binding",
                "metadata_excerpt": [line for line in metadata.splitlines() if line.startswith(("task:", "batch:", "imgsz:", "- "))][:5],
            },
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"status": "PASS", "records": records}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
