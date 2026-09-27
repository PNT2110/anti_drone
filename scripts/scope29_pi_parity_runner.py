#!/usr/bin/env python3
"""Scope 29 pre-live eight-image HIGH-stream parity gate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2

from scope28_pi_runner import FrozenNcnnDetector
from anti_drone.scope28_contract import compare_detections


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    cfg = json.loads(Path("config.json").read_text())
    model = Path(cfg["model_dir"])
    if sha256(model / "model.ncnn.param") != cfg["param_sha256"] or sha256(model / "model.ncnn.bin") != cfg["bin_sha256"]:
        raise SystemExit("DETECTOR_ARTIFACT_HASH_FAIL")
    reference = json.loads(Path(cfg["reference"]).read_text())
    ref = {(row["run_id"], row["image"]): row for row in reference["records"]}
    detector = FrozenNcnnDetector(model)
    rows = []
    for item in cfg["images"]:
        image = cv2.imread(str(Path(cfg["input_root"]) / item["filename"]))
        if image is None:
            rows.append({"image": item["filename"], "status": "IMAGE_READ_FAIL"})
            continue
        result = detector.infer_dual(image)
        comparison = compare_detections(ref[(cfg["run_id"], item["filename"])]["detections"], result["high"])
        rows.append({"image": item["filename"], "comparison": comparison, "contract": result["contract"]})
    status = "PARITY_PASS" if len(rows) == 8 and all(row.get("comparison", {}).get("status") == "PARITY_PASS" for row in rows) else "PARITY_FAIL"
    output = {"status": status, "candidate_id": cfg["candidate_id"], "images": rows, "single_inference_per_image": True, "one_nms_per_image": True, "test_accessed": False}
    Path(cfg["output"]).write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2), flush=True)
    return 0 if status == "PARITY_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
