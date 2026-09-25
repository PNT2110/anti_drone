"""Create data.yaml only after the independent Scope 17 audit passes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
AUDIT = ROOT / ".runtime/scope17/label_repair_audit.json"
OUT = ROOT / ".runtime/scope17/finalization.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS" or not audit.get("label_ready"):
        raise RuntimeError("BLOCKED: Scope 17 direct repair audit is not PASS")
    data_yaml = DATASET / "data.yaml"
    if data_yaml.exists():
        raise RuntimeError("BLOCKED: refusing to overwrite existing repair data.yaml")
    manifest = DATASET / "manifest.json"
    registry = DATASET / "split_registry.json"
    data_yaml.write_text(
        f"path: {DATASET}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: drone\n",
        encoding="utf-8",
    )
    result = {
        "status": "PASS",
        "label_ready": True,
        "training_run": False,
        "data_yaml": str(data_yaml),
        "manifest_sha256": sha256(manifest),
        "split_registry_sha256": sha256(registry),
        "direct_audit_sha256": sha256(AUDIT),
        "source_v3_manifest_sha256": "b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc",
        "source_v3_split_registry_sha256": "57ffb56effd35ad65aad9d163e586ebd8c9f9f1f19c93a86d5fd7619d72cff3d",
        "production_status": "CANDIDATE_ONLY",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
