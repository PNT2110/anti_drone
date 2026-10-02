from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (ROOT / "artifacts").resolve()
REMOVE = {"benchmarks", "experiments", "exports", "integration", "maintenance", "transfer_cache"}
KEEP = {"deploy", "deploy-320", "production-candidate", "releases", "models"}

if ARTIFACTS.parent != ROOT or not ARTIFACTS.is_dir():
    raise SystemExit(f"Unexpected artifacts root: {ARTIFACTS}")
if REMOVE & KEEP:
    raise SystemExit("Remove/keep sets overlap")

removed = []
for name in sorted(REMOVE):
    target = (ARTIFACTS / name).resolve()
    if target.parent != ARTIFACTS:
        raise SystemExit(f"Refusing out-of-scope target: {target}")
    if target.exists():
        shutil.rmtree(target)
        removed.append(name)
print("removed=" + ",".join(removed))
print("preserved=" + ",".join(sorted(KEEP)))
