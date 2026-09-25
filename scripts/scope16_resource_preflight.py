"""Read-only Scope 16 environment/resource preflight."""

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
OUT = ROOT / ".runtime/scope16/resource_preflight.json"
DATA = ROOT / "data/processed/drone-single-class-v3-candidate/data.yaml"
CONFIG_DIR = ROOT / "configs/training/scope15"
OUTPUT_ROOT = ROOT / "artifacts/experiments/scope16-v3"
WEIGHTS = {
    "yolov8n": Path("/home/pnt/Desktop/antidrone/model/yolov8n.pt"),
    "yolov11n": Path("/home/pnt/Desktop/antidrone/model/yolo11n.pt"),
    "yolo26n": Path("/home/pnt/Desktop/antidrone/model/yolo26n.pt"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gpu_info() -> dict:
    try:
        output = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu", "--format=csv,noheader,nounits"], text=True).strip()
        fields = [value.strip() for value in output.splitlines()[0].split(",")]
        return {"name": fields[0], "memory_total_mib": int(fields[1]), "memory_used_mib": int(fields[2]), "memory_free_mib": int(fields[3]), "utilization_percent": int(fields[4])}
    except Exception as exc:
        return {"error": str(exc)}


def active_training_processes() -> list[str]:
    found = []
    proc = Path("/proc")
    for directory in proc.iterdir():
        if not directory.name.isdigit():
            continue
        try:
            command = (directory / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
        except OSError:
            continue
        if any(token in command for token in ("train_gpu.py", "ultralytics.engine.trainer", "yolo train")):
            found.append(command)
    return found


def memory_info() -> dict[str, int]:
    values = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, raw = line.split(":", 1)
        fields = raw.strip().split()
        if fields and fields[0].isdigit():
            values[key] = int(fields[0]) * (1024 if len(fields) > 1 and fields[1] == "kB" else 1)
    return {"total_bytes": values.get("MemTotal", 0), "available_bytes": values.get("MemAvailable", 0)}


def main() -> int:
    config_paths = sorted(CONFIG_DIR.glob("*.json"))
    result = {
        "status": "NOT_RUN_DUE_TO_LABEL_PREFLIGHT_BLOCK",
        "training_started": False,
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "gpu": gpu_info(),
        "system_memory": memory_info(),
        "disk": {"free_bytes": shutil.disk_usage(ROOT).free, "total_bytes": shutil.disk_usage(ROOT).total},
        "active_training_processes": active_training_processes(),
        "data_yaml_exists": DATA.is_file(),
        "scope15_config_count": len(config_paths),
        "scope15_configs": [str(path) for path in config_paths],
        "weights": {key: {"path": str(path), "exists": path.is_file(), "sha256": sha256(path) if path.is_file() else None} for key, path in WEIGHTS.items()},
        "scope16_output_exists": OUTPUT_ROOT.exists(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
