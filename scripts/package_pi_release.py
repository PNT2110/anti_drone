#!/usr/bin/env python3
"""Package the verified host artifacts into a reproducible Pi handoff bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="yolov8n")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/releases/yolov8n"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    deployment = root / "artifacts/deploy" / args.model_id
    if not (deployment / "metadata.json").exists() or json.loads((deployment / "parity.json").read_text()).get("status") != "DONE":
        raise RuntimeError("Deployment parity is not DONE; refusing to package")
    files = [
        (deployment, Path("artifacts/deploy") / args.model_id),
        (root / "src/anti_drone/runtime.py", Path("src/anti_drone/runtime.py")),
        (root / "scripts/run_phase5.py", Path("scripts/run_phase5.py")),
        (root / "scripts/benchmark_phase6.py", Path("scripts/benchmark_phase6.py")),
        (root / "scripts/promote_pi_release.py", Path("scripts/promote_pi_release.py")),
        (root / "requirements-pi.txt", Path("requirements-pi.txt")),
        (root / "docs/PI5_HANDOFF.md", Path("docs/PI5_HANDOFF.md")),
    ]
    parity_set = root / ".runtime/parity-set"
    if parity_set.exists():
        files.append((parity_set, Path(".runtime/parity-set")))
    bundle_name = f"anti-drone-{args.model_id}-pi5.tar.gz"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = args.output_dir / bundle_name
    manifest = {"model_id": args.model_id, "status": "HOST_VERIFIED_PI_HANDOFF", "files": [], "created_unix": time.time()}
    with tarfile.open(bundle_path, "w:gz") as archive:
        for source, archive_path in files:
            if not source.exists():
                raise FileNotFoundError(source)
            if source.is_file():
                archive.add(source, arcname=Path("anti-drone") / archive_path)
                manifest["files"].append({"path": str(archive_path), "sha256": sha256(source), "size": source.stat().st_size})
            else:
                for item in sorted(source.rglob("*")):
                    if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc":
                        relative = archive_path / item.relative_to(source)
                        archive.add(item, arcname=Path("anti-drone") / relative)
                        manifest["files"].append({"path": str(relative), "sha256": sha256(item), "size": item.stat().st_size})
    manifest["bundle_sha256"] = sha256(bundle_path)
    manifest_path = args.output_dir / "PI5_BUNDLE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "PI5_BUNDLE.md").write_text(
        f"# Pi 5 deployment bundle — {args.model_id}\n\n"
        "Status: `HOST_VERIFIED_PI_HANDOFF`\n\n"
        f"Bundle: `{bundle_name}`\n\n"
        f"Bundle SHA256: `{manifest['bundle_sha256']}`\n\n"
        "This bundle contains verified model/runtime files but does not claim Pi "
        "camera or thermal acceptance. Follow `docs/PI5_HANDOFF.md` on the Pi.\n",
        encoding="utf-8",
    )
    print(json.dumps({"bundle": str(bundle_path), "manifest": str(manifest_path), "sha256": manifest["bundle_sha256"], "files": len(manifest["files"])}, indent=2))


if __name__ == "__main__":
    main()
