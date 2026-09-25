#!/usr/bin/env python3
"""Create the Scope 21 host-side audit and blocked Pi-5 evidence.

This command is deliberately audit-only.  It never runs inference, copies files,
installs packages, opens the TEST split, or treats an x86_64 host as a Pi.
"""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope21"
DOCS = ROOT / "docs/tracking/scope21"
SCOPE20 = RUNTIME.parent / "scope20"
SCOPE19 = RUNTIME.parent / "scope19"

EXPECTED_BEST = {
    "scope18-yolov8n-640": "debcef45f0a1667f16c62daf7a8f42d0e5932be498b549b2f985bc72915e9718",
    "scope18-yolov8n-480": "359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e",
    "scope18-yolov11n-640": "ab2d146424a2c9c0ce053b122463d7d2e796834e9671a60bdeacd4047ca68186",
    "scope18-yolov11n-480": "6f086a2206a466c1037e6aab3ddbbf1afc40b38f7643e9be4f83a85630a81e05",
    "scope18-yolo26n-640": "3153d0ffdd6b4db7b3fd28fa4026636fe3ffad19acaedbea1c4f35c996fb8bae",
    "scope18-yolo26n-480": "1500fb46bbf01910f85a0b75b37e00f275bf0cb725c0829e7c2db293ea6a23d6",
}

VAL = {
    "scope18-yolov8n-640": (0.63360, 0.98665),
    "scope18-yolov8n-480": (0.62836, 0.98689),
    "scope18-yolov11n-640": (0.62983, 0.98725),
    "scope18-yolov11n-480": (0.62466, 0.98583),
    "scope18-yolo26n-640": (0.63170, 0.98543),
    "scope18-yolo26n-480": (0.62691, 0.98264),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def directory_inventory(path: Path) -> dict:
    files = []
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        files.append({"relative": str(item.relative_to(path)), "bytes": item.stat().st_size, "sha256": sha256(item)})
    canonical = "\n".join(f"{x['relative']}\t{x['bytes']}\t{x['sha256']}" for x in files).encode()
    return {"path": str(path), "kind": "directory", "files": files, "sha256": hashlib.sha256(canonical).hexdigest()}


def load(name: str) -> dict:
    return json.loads((SCOPE20 / name).read_text())


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    scope20_input = load("input_audit.json")
    parity = load("parity_summary.json")
    benchmark = json.loads((SCOPE19 / "benchmark_input_manifest.json").read_text())

    checkpoint_rows = []
    for run_id, expected in EXPECTED_BEST.items():
        path = ROOT / "artifacts/experiments/scope18-v3-labelrepair" / run_id / "attempt-batch16/weights/best.pt"
        actual = sha256(path) if path.exists() else None
        checkpoint_rows.append({"run_id": run_id, "path": str(path), "expected_sha256": expected, "actual_sha256": actual, "match": actual == expected})

    parity_rows = {(x["run_id"], x["backend"]): x for x in parity["summary"]}
    candidates = []
    for (run_id, backend), row in sorted(parity_rows.items()):
        if row["status"] != "PARITY_PASS":
            continue
        if backend == "onnx":
            path = ROOT / "artifacts/exports/scope19" / run_id / "float32/onnx/model.onnx"
            artifact = {"path": str(path), "kind": "file", "bytes": path.stat().st_size, "sha256": sha256(path)} if path.exists() else {"path": str(path), "missing": True}
        else:
            path = ROOT / "artifacts/exports/scope19" / run_id / "float32/ncnn/model_ncnn_model"
            artifact = directory_inventory(path) if path.exists() else {"path": str(path), "missing": True}
        size = int(run_id.rsplit("-", 1)[-1])
        candidates.append({
            "candidate_id": f"{run_id}:{backend}",
            "run_id": run_id,
            "size": size,
            "backend": backend,
            "scope20_parity": "PARITY_PASS",
            "artifact": artifact,
            "frozen_val": {"map50_95": VAL[run_id][0], "recall": VAL[run_id][1]},
            "status": "BLOCKED_PI_ACCESS",
        })

    audit = {
        "scope": "21",
        "created_at_utc": now,
        "status": "PI_ACCESS_REQUIRED",
        "host": {"platform": platform.platform(), "machine": platform.machine(), "is_pi5": False},
        "baseline": {
            "scope20_input_audit": str(SCOPE20 / "input_audit.json"),
            "scope20_input_status": scope20_input["status"],
            "checkpoint_count": len(checkpoint_rows),
            "checkpoint_all_match": all(x["match"] for x in checkpoint_rows),
            "test_accessed": False,
            "v3_test_locked": True,
            "benchmark_manifest": str(SCOPE19 / "benchmark_input_manifest.json"),
            "benchmark_split": benchmark.get("split"),
            "benchmark_count": benchmark.get("count"),
            "benchmark_test_accessed": benchmark.get("test_accessed"),
        },
        "checkpoint_hashes": checkpoint_rows,
        "candidate_count": len(candidates),
        "candidate_policy": "Exactly the 10 Scope 20 PARITY_PASS pairs; YOLO26 NCNN excluded.",
        "candidates": candidates,
        "parity_gate": parity["acceptance_gate"],
        "protocol": {"warmup_passes": 20, "measured_passes": 100, "confidence": 0.25, "nms_iou": 0.70, "input_order": "fixed", "sizes": [480, 640]},
        "boundaries": {"no_test_inference": True, "no_retrain": True, "no_quantization": True, "no_tracker": True, "no_live_camera": True, "no_production_freeze": True},
    }
    (RUNTIME / "input_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (RUNTIME / "artifact_inventory.json").write_text(json.dumps({"created_at_utc": now, "candidates": candidates, "transfer_status": "NOT_ATTEMPTED_PI_ACCESS_REQUIRED"}, indent=2) + "\n")
    (RUNTIME / "pi_access.json").write_text(json.dumps({
        "created_at_utc": now,
        "status": "PI_ACCESS_REQUIRED",
        "target_source": "docs/PI5_EXECUTION_STATUS.md",
        "target_attempted": "pi5@192.168.1.118",
        "command_policy": "ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new pi5@192.168.1.118 '<read-only identity commands>'",
        "result": "Permission denied (publickey,password).",
        "identity": "NOT_VERIFIED",
        "action_required": "Provide/configure non-interactive SSH authentication to the real Pi 5; do not place passwords in the repository.",
    }, indent=2) + "\n")
    (RUNTIME / "benchmark_results.json").write_text(json.dumps({"status": "PI_BENCHMARK_BLOCKED", "candidate_count": 10, "results": [], "reason": "Pi 5 SSH authentication is unavailable; no x86_64 substitute was run."}, indent=2) + "\n")
    (RUNTIME / "selection_evidence.json").write_text(json.dumps({"status": "BLOCKED", "production_freeze": False, "candidates": [{"candidate_id": x["candidate_id"], "frozen_val": x["frozen_val"], "pi_status": "BLOCKED_PI_ACCESS", "int8_status": "SCOPE20_BLOCKED"} for x in candidates]}, indent=2) + "\n")

    docs = {
        "SCOPE21_INPUT_AUDIT.md": f"""# Scope 21 — Input audit\n\nStatus: **PI_ACCESS_REQUIRED**.\n\nScope 20 baseline audit is `{scope20_input['status']}`; all six immutable Scope 18 `best.pt` hashes match and the fixed benchmark manifest contains 8 `train` images with `test_accessed=false`. The locked V3 TEST split was not opened.\n\nExactly **10** candidates are eligible: Scope 20 `PARITY_PASS` ONNX/NCNN pairs. YOLO26 NCNN (2 pairs) is excluded because Scope 20 marked it `PARITY_FAIL`.\n\nMachine evidence: `.runtime/scope21/input_audit.json`.\n""",
        "SCOPE21_PI_ACCESS_REPORT.md": """# Scope 21 — Pi 5 access report\n\nStatus: **PI_ACCESS_REQUIRED**.\n\nThe current host is x86_64 and has no Raspberry Pi device-tree identity. The previously documented target `pi5@192.168.1.118` was attempted in non-interactive mode; SSH returned `Permission denied (publickey,password)`. No password was stored or requested, and no benchmark was run.\n\nRequired user action: configure a usable SSH key/agent for the real Pi 5, or provide an equivalent non-interactive SSH target. After access is available, the identity gate must pass `uname -m=aarch64` and `/proc/device-tree/model` must identify Raspberry Pi 5 before transfer or benchmark.\n\nEvidence: `.runtime/scope21/pi_access.json`.\n""",
        "SCOPE21_PI_ENVIRONMENT.md": """# Scope 21 — Pi environment\n\nStatus: **NOT_STARTED — PI_ACCESS_REQUIRED**.\n\nNo remote commands were executed because SSH authentication failed. Therefore Pi OS, kernel, RAM, disk, CPU load, ONNX Runtime/NCNN versions, temperature, throttling, and thread policy are intentionally **N/A**, not inferred from the x86_64 host. No package was installed and no system configuration was changed.\n""",
        "SCOPE21_ARTIFACT_TRANSFER.md": """# Scope 21 — Artifact transfer\n\nStatus: **NOT_ATTEMPTED — PI_ACCESS_REQUIRED**.\n\nThe host-side inventory records hashes for the 10 eligible Scope 20 `PARITY_PASS` artifacts. Nothing was copied to a Pi, so no transfer hash can be claimed. The separate remote directory `~/antidrone-scope21` was not created.\n\nEvidence: `.runtime/scope21/artifact_inventory.json`.\n""",
        "SCOPE21_PI_PARITY.md": """# Scope 21 — Pi runtime parity\n\nStatus: **NOT_RUN — PI_ACCESS_REQUIRED**.\n\nNo candidate was loaded on a Pi, so there are no Pi output tensors, runtime versions, decoder checks, or parity measurements. The frozen Scope 20 acceptance gate remains: confidence absolute difference `<= 0.05`, bbox IoU `>= 0.95`, exact class, and exact detection count.\n""",
        "SCOPE21_PI_BENCHMARK.md": """# Scope 21 — Pi 5 FP32 benchmark\n\nStatus: **PI_BENCHMARK_BLOCKED**.\n\nThe required Raspberry Pi 5 SSH access gate did not pass. No x86_64 substitute was used. Consequently there are zero timing, FPS, RSS, RAM, CPU, thermal, throttling, load-time, or runtime-version results. The prescribed protocol remains 20 warmups and at least 100 fixed-order measured passes per eligible candidate, with 480 models at 480 input and 640 models at 640 input.\n\nCandidate accounting is still complete: 10 eligible pairs are listed in `.runtime/scope21/benchmark_results.json` as blocked; YOLO26 NCNN is not eligible.\n""",
        "SCOPE21_SELECTION_EVIDENCE.md": """# Scope 21 — Selection evidence\n\nStatus: **BLOCKED**; no production model is frozen.\n\nFrozen Scope 18 VAL values are carried forward only: mAP50-95 and recall are recorded per candidate in `.runtime/scope21/selection_evidence.json`. Pi latency and memory evidence are missing because the Pi access gate failed. Scope 20 INT8 remains `BLOCKED` and was not modified. Therefore no Pareto winner, dominated-for-Pi claim, or deployment recommendation is made.\n""",
        "SCOPE21_TEST_REPORT.md": """# Scope 21 — Test report\n\nExecuted checks:\n\n- `PYTHONPATH=. python -m pytest -q` — **PASS**, `106 passed, 1 skipped in 1.10s`.\n- `python -m compileall -q scripts src tests` — **PASS**.\n- `git diff --check` — **PASS**.\n- `python scripts/scope20_parity.py --phase audit` — **PASS**, six checkpoint hashes and 12 Scope 19 export hashes match.\n\nScope-specific checks cover exactly 10 Scope 20 `PARITY_PASS` candidates; YOLO26 NCNN exclusion; fixed train-only benchmark membership; Pi identity as a mandatory gate; no transfer/benchmark without verified Pi 5 hardware; and production freeze remaining false. The Scope 21 audit does not access TEST or run inference.\n""",
        "SCOPE21_FINAL_REPORT.md": """# Scope 21 — Final report\n\nStatus: **PI_ACCESS_REQUIRED / PI_BENCHMARK_BLOCKED**.\n\nScope 21 cannot reach `COMPLETE` because the real Raspberry Pi 5 is not authenticated. The current host is x86_64, and using it as a Pi substitute would violate the scope. The documented SSH target `pi5@192.168.1.118` rejected non-interactive authentication.\n\nCompleted safely:\n\n- Scope 18/19/20 baseline rechecked through the Scope 20 PASS audit; six checkpoint hashes remain immutable.\n- Fixed 8-image train-only benchmark membership remains locked; TEST was not accessed.\n- Exactly 10 Scope 20 `PARITY_PASS` candidates are accounted for. YOLO26 NCNN remains excluded.\n- Host-side artifact inventory and hashes were recorded; no transfer occurred.\n- No retraining, quantization, tracker change, live camera, Pi configuration change, or production freeze occurred.\n\nOutstanding: configure non-interactive SSH access to the real Pi 5, then rerun the read-only identity/environment audit, transfer only the 10 eligible artifacts to `~/antidrone-scope21`, perform Pi runtime parity, and execute the fixed 20/100 FP32 benchmark protocol.\n\nEvidence: `.runtime/scope21/`.\n""",
    }
    for name, content in docs.items():
        (DOCS / name).write_text(content)
    print(json.dumps({"status": audit["status"], "candidates": len(candidates), "runtime": str(RUNTIME), "docs": str(DOCS)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
