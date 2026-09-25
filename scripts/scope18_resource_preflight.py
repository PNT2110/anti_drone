"""Scope 18 read-only resource and environment preflight."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

import torch
import ultralytics


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".runtime/scope18/resource_preflight.json"
OUTPUT_ROOT = ROOT / "artifacts/experiments/scope18-v3-labelrepair"
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
WEIGHTS = {
    "yolov8n": (Path("/home/pnt/Desktop/antidrone/model/yolov8n.pt"), "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36"),
    "yolov11n": (Path("/home/pnt/Desktop/antidrone/model/yolo11n.pt"), "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"),
    "yolo26n": (Path("/home/pnt/Desktop/antidrone/model/yolo26n.pt"), "9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef"),

}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def meminfo() -> dict[str, int]:
    values = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, raw = line.split(":", 1)
        parts = raw.strip().split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0]) * (1024 if len(parts) > 1 and parts[1] == "kB" else 1)
    return {"total_bytes": values.get("MemTotal", 0), "available_bytes": values.get("MemAvailable", 0)}


def gpu() -> dict:
    try:
        raw = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu", "--format=csv,noheader,nounits"], text=True).strip().splitlines()[0]
        name, total, used, free, util = [part.strip() for part in raw.split(",")]
        return {"name": name, "memory_total_mib": int(total), "memory_used_mib": int(used), "memory_free_mib": int(free), "utilization_percent": int(util)}
    except Exception as exc:
        return {"error": str(exc)}


def active_scope_processes() -> list[str]:
    result = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        if int(proc.name) == os.getpid():
            continue
        try:
            command = proc.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
        except OSError:
            continue
        # A shell command used to invoke this read-only check may contain a
        # later `scope18_training.py --help` token.  That is not an active
        # training process; only count the real runner, never its help call.
        active_runner = any(token in command and "--help" not in command for token in ("train_gpu.py", "scope18_training.py"))
        if active_runner or "ultralytics.engine.trainer" in command:
            result.append(command)
    return result


def main() -> int:
    gpu_state = gpu()
    gpu_busy = gpu_state.get("utilization_percent", 100) > 50 or gpu_state.get("memory_used_mib", 12288) > gpu_state.get("memory_total_mib", 12288) * 0.5
    weights = {key: {"path": str(path), "exists": path.is_file(), "sha256": sha256(path) if path.is_file() else None, "expected": expected, "match": path.is_file() and sha256(path) == expected} for key, (path, expected) in WEIGHTS.items()}
    configs = sorted((ROOT / "configs/training/scope18").glob("*.json"))
    errors = []
    if not torch.cuda.is_available():
        errors.append("CUDA unavailable")
    if gpu_busy:
        errors.append("GPU busy above Scope 18 threshold")
    if active_scope_processes():
        errors.append("existing training process detected")
    if OUTPUT_ROOT.exists():
        errors.append("Scope 18 output root already exists")
    if not all(item["match"] for item in weights.values()):
        errors.append("starting weight checksum mismatch")
    if len(configs) != 6:
        errors.append(f"expected 6 configs, found {len(configs)}")
    disk = shutil.disk_usage(ROOT)
    result = {"status": "PASS" if not errors else "RESOURCE_BLOCKED", "errors": errors, "training_started": False, "python": platform.python_version(), "torch": torch.__version__, "ultralytics": ultralytics.__version__, "cuda_version": torch.version.cuda, "cuda_available": torch.cuda.is_available(), "gpu": gpu_state, "system_memory": meminfo(), "disk": {"total_bytes": disk.total, "free_bytes": disk.free}, "dataset": str(DATASET), "data_yaml": str(DATASET / "data.yaml"), "configs": [str(path) for path in configs], "weights": weights, "active_scope_processes": active_scope_processes(), "output_root_exists": OUTPUT_ROOT.exists()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
