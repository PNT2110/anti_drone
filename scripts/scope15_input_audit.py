"""Lock and verify the Scope 15 baseline inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".runtime/scope15/input_baseline.json"
FILES = {
    "v1_manifest": (ROOT / "data/processed/drone-single-class/manifest.json", "3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d"),
    "v1_split_registry": (ROOT / "data/processed/drone-single-class/split_registry.json", "7bc14c2e05b690f2df6c0cfb92e03b565a200f16dd0ef110df8e464837a63a54"),
    "v2_manifest": (ROOT / "data/processed/drone-single-class-v2/manifest.json", "9605532a2b24566b691554125074c37f198c452bce343883b2a6720847299aa1"),
    "v2_split_registry": (ROOT / "data/processed/drone-single-class-v2/split_registry.json", "5819f6df78156561f3907e0eac05186dd5d77fe556699c74bad0ee5d40f51ed9"),
    "v2_audit": (ROOT / "data/processed/drone-single-class-v2/audit.json", "ab6a02db3b5efdff5f4c95d130ab4f9b06eddd18b9541aa7157ebb86f016a120"),
    "v2_executable_manifest": (ROOT / "data/processed/drone-single-class-v2-executable/manifest.json", "c66e201aae060b96687c841d54a3297a1ea9fe7788d9101521bffe87f43db9aa"),
    "v2_executable_data_yaml": (ROOT / "data/processed/drone-single-class-v2-executable/data.yaml", "38dabc580af21f5ed36f1d578f6b00c99f7efc9300ae72d105c6d44909cf8216"),
    "scope13_mapping": (ROOT / ".runtime/scope13/rgbt_archive_mapping.csv", "ffb0d14247ff02f9d30e14011769435fd296103e4fe735e02abbb30cd1396d4e"),
    "scope14_conservative_csv": (ROOT / ".runtime/scope14/v3_dry_run_b_conservative.csv", "eb045f9d0c9f6f247e092b3b8c45389d80a495c7a26e2f8523554dd89b6afa57"),
    "scope14_audit": (ROOT / ".runtime/scope14/v3_dry_run_audit.json", "cf20f29f4e1646b0e1b6ae62f538bae7785a0437bd9ed4afff0d72ff5ada168b"),
    "v1_checkpoint": (ROOT / "artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2/weights/best.pt", "662fbc1c066041345970f4211a6ceb9209907a331fd1724c0b2be7e53a4beec1"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    observed = {}
    errors = []
    for key, (path, expected) in FILES.items():
        if not path.is_file():
            errors.append(f"missing: {path}")
            continue
        actual = sha256(path)
        observed[key] = {"path": str(path), "sha256": actual, "expected": expected, "match": actual == expected}
        if actual != expected:
            errors.append(f"checksum mismatch: {key}")
    result = {"status": "PASS" if not errors else "BLOCKED", "errors": errors, "files": observed, "training_run": False}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
