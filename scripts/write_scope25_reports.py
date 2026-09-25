#!/usr/bin/env python3
"""Write Scope 25 freeze-review reports without creating a package on failure."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope25"
DOCS = ROOT / "docs/tracking/scope25"


def read(name):
    return json.loads((RUNTIME / name).read_text())


def write(name, body):
    (DOCS / name).write_text(body.rstrip() + "\n")


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    audit = read("input_audit.json")
    pi = read("pi_reproduction.json")
    summary = {"status": "FREEZE_REPRODUCTION_BLOCKED", "candidate_id": audit["candidate_id"], "selected_deployment_candidate": False, "package_created": False, "freeze_manifest_created": False, "test_accessed": False, "reason": pi["reason"]}
    (RUNTIME / "freeze_status.json").write_text(json.dumps(summary, indent=2) + "\n")

    write("SCOPE25_INPUT_AUDIT.md", """# Scope 25 — Input audit

Status: **INPUTS VERIFIED; FREEZE BLOCKED AT PI REPRODUCTION**.

- Primary review candidate: `scope18-yolov8n-480:ncnn`.
- `best.pt` SHA-256: `359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e` — exact match.
- NCNN `.param` SHA-256: `8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5` — exact match.
- NCNN `.bin` SHA-256: `23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7` — exact match.
- Scope 20 NCNN parity: `PARITY_PASS`.
- Scope 21 Pi evidence: `PI_BENCHMARK_PASS`, 22.493 FPS, NCNN 1.0.20260526, 4 threads.
- Dataset manifest SHA-256: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`.
- Split registry SHA-256: `c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1`.
- Fixed smoke input set: 8 TRAIN images; `test_accessed=false`.

Machine-readable audit: [`input_audit.json`](../../../.runtime/scope25/input_audit.json).
""")

    write("SCOPE25_FREEZE_DECISION.md", """# Scope 25 — Freeze decision

The declared primary candidate remains `YOLOv8n-480 / NCNN / FP32 / 480`. Historical evidence supports it under current constraints: VAL mAP50-95 `0.62836`, VAL recall `0.98689`, Pi FPS `22.493`, Scope 21 parity PASS, no throttling, and PTQ INT8 exhausted.

This is not a freeze yet. The required Scope 25 Pi reproduction smoke could not run because the Pi was unreachable. Therefore no `SELECTED_DEPLOYMENT_CANDIDATE` status is asserted and no alternative candidate was selected silently.
""")

    write("SCOPE25_MODEL_CONTRACT.md", """# Scope 25 — Model contract (freeze pending)

Intended candidate contract, already verified against the Scope 19/21 NCNN artifact:

- Backend: NCNN FP32, version `1.0.20260526`, 4 threads.
- Input: BGR → RGB → `rect=False` letterbox, padding 114 → 480×480 → float32 `/255` → NCHW → batch 1.
- Output: `[1,5,N]`, `xywh` plus single-class score, class 0.
- Confidence threshold: `0.25`.
- External NMS: exactly once, IoU `0.70`.

The contract is not promoted to a production package until the Pi smoke gate passes.
""")

    write("SCOPE25_PI_REPRODUCTION.md", """# Scope 25 — Pi reproduction

Status: **`FREEZE_REPRODUCTION_BLOCKED`**.

The smoke transfer was attempted to a separate Scope 25 path using the verified NCNN pair and fixed 8-image TRAIN subset. Four connection checks were made. SSH port 22 was unreachable, ping received no replies, and the ARP neighbor state was `INCOMPLETE`.

No model was copied, no Pi runtime was changed, no inference was run, and no temperature/throttling result was collected in Scope 25. Scope 21 historical evidence remains valid but does not substitute for this required reproduction gate.

Machine-readable record: [`pi_reproduction.json`](../../../.runtime/scope25/pi_reproduction.json).
""")

    write("SCOPE25_PRODUCTION_PACKAGE.md", """# Scope 25 — Production package

**NOT CREATED.**

The package directory `artifacts/production-candidate/scope25/` and freeze manifest were intentionally not created because the required Pi reproduction smoke did not pass. Verified source artifacts remain in their original Scope 19 locations and were not moved or overwritten.
""")

    write("SCOPE25_TEST_LOCK.md", """# Scope 25 — TEST lock

`V3 TEST` remained locked. No TEST image was read, no test metrics were run, and no threshold was tuned. `SESSION_DISJOINT` remains UNVERIFIED and the checkpoint state remains `SPLIT_UNVERIFIED`.
""")

    write("SCOPE25_TEST_REPORT.md", """# Scope 25 — Test report

Regression guards verify the exact v8n-480 NCNN candidate, checkpoint/export hashes, 480 image size, preprocessing/postprocessing thresholds, TRAIN-only smoke membership, TEST exclusion, absence of a package after blocked reproduction, preservation of non-selected artifacts, and no tracker integration.

Required commands:

```text
python -m pytest -q
python -m compileall -q scripts src tests
git diff --check
```
""")

    write("SCOPE25_FINAL_REPORT.md", """# Scope 25 — Final report

## Status

**`FREEZE_REPRODUCTION_BLOCKED`** — Scope 25 did not reach `FP32_NCNN_CANDIDATE_FROZEN`.

The exact requested primary candidate and all source hashes passed local verification. The historical Scope 20/21 parity and Pi benchmark evidence also passed. However, the mandatory current Pi reproduction smoke could not connect to `192.168.1.118`; therefore the acceptance gate is incomplete.

No production package, freeze manifest, Pi transfer, or production freeze was created. No TEST evaluation, retraining, INT8 work, dataset/split change, tracker/camera/servo work, or Git commit/push occurred.

Resume Scope 25 only after Pi SSH/network access is restored, then rerun the smoke against the same verified hashes. Do not open TEST before the freeze gate passes.
""")


if __name__ == "__main__":
    main()
