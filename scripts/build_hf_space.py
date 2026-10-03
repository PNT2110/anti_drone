"""Assemble the upload bundle for the Hugging Face Space.

Usage (from the repository root):
    python scripts/build_hf_space.py
    hf upload <user>/<space> dist/hf-space . --repo-type space
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
TEMPLATE = ROOT / "deploy" / "hf-space"
OUTPUT = ROOT / "dist" / "hf-space"

WEB_FILES = ["app.py", "security.py"]
WEB_DIRS = ["backend", "static", "templates"]
# The Space has no onnxruntime, so only the PyTorch checkpoints are shipped.
MODEL_GLOB = "drone-*-fresh-*.pt"


def main() -> int:
    # Clear old files but keep the directories: on Windows an open Explorer or
    # editor window on the bundle makes removing the folders themselves fail.
    if OUTPUT.exists():
        for path in OUTPUT.rglob("*"):
            if path.is_file():
                path.unlink()
    bundle_web = OUTPUT / "web"
    bundle_web.mkdir(parents=True, exist_ok=True)

    for name in ("Dockerfile", "README.md", "requirements.txt"):
        shutil.copy2(TEMPLATE / name, OUTPUT / name)
    for name in WEB_FILES:
        shutil.copy2(WEB / name, bundle_web / name)
    for name in WEB_DIRS:
        shutil.copytree(
            WEB / name,
            bundle_web / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            dirs_exist_ok=True,
        )

    models = sorted((WEB / "models").glob(MODEL_GLOB))
    if not models:
        raise SystemExit(f"No model matching {MODEL_GLOB} in {WEB / 'models'}")
    (bundle_web / "models").mkdir(exist_ok=True)
    for model in models:
        shutil.copy2(model, bundle_web / "models" / model.name)

    files = [path for path in OUTPUT.rglob("*") if path.is_file()]
    size_mb = sum(path.stat().st_size for path in files) / (1024 * 1024)
    print(f"Bundle: {OUTPUT} ({len(files)} files, {size_mb:.1f} MB, {len(models)} models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
