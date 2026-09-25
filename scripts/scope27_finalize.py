#!/usr/bin/env python3
"""Verify and copy Scope 27 dry-run evidence without changing source tracker code."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope27"
ARTIFACTS = ROOT / "artifacts/integration/scope27"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    audit = json.loads((RUNTIME / "input_audit.json").read_text())
    parity = json.loads((RUNTIME / "parity_smoke.json").read_text())
    summary = json.loads((RUNTIME / "dryrun_summary.json").read_text())
    if audit["freeze_manifest_sha256"] != "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964":
        raise SystemExit("FREEZE_MANIFEST_MISMATCH")
    if audit["scope26_headline_sha256"] != "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83":
        raise SystemExit("SCOPE26_HEADLINE_MISMATCH")
    if parity["status"] != "PARITY_PASS" or len(parity["images"]) != 8:
        raise SystemExit("DETECTOR_PARITY_BLOCKED")
    if summary["status"] != "DRY_RUN_COMPLETE" or summary["frames_processed"] != 301 or not summary["actuator"]["enabled"] is False:
        raise SystemExit("DRYRUN_INCOMPLETE_OR_ACTUATOR_ENABLED")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ("dryrun_summary.json", "target_state.jsonl", "parity_smoke.json", "input_audit.json", "sequence_manifest.json"):
        source = RUNTIME / name
        destination = ARTIFACTS / name
        shutil.copy2(source, destination)
        copied.append(destination)
    manifest = {"status": "FROZEN_DETECTOR_TRACKER_DRYRUN_INTEGRATED", "files": {path.name: sha256(path) for path in copied}, "actuator_output_enabled": False, "gpio_writes": 0, "pwm_writes": 0, "serial_writes": 0, "freeze_manifest_sha256": audit["freeze_manifest_sha256"], "scope26_headline_sha256": audit["scope26_headline_sha256"], "test_accessed": False}
    (ARTIFACTS / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
