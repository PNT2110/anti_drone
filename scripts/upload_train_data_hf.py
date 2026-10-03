"""Upload the datasets to Hugging Face.

Two things make a plain folder upload of data/ impossible:
- the Hub silently skips every file matched by the repo's .gitignore, and
  ours ignores data/** (the commit succeeds, the file is just not there);
- the Hub refuses folders with more than 10,000 files, and images/train
  alone has 63,028.

So data_train is packed into one tar per split, and everything goes under
dataset_archives/, a path the .gitignore does not match.

Usage (from the repository root):
    python scripts/upload_train_data_hf.py pnt2110/anti_done [--with-source-archives]
"""

from __future__ import annotations

import argparse
import tarfile
import time
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "data_train"
SOURCE_ARCHIVES = ROOT / "data" / "import_data_rar"
PACK_DIR = ROOT / "dist" / "data_train_pack"
REMOTE_ROOT = "dataset_archives"
SPLITS = ("test", "val", "train")
SMALL_FILES = ("data.yaml", "manifest.json", "import_archives_manifest.json", "license_ledger.json")
ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tar.xz", ".tgz")


def pack(split: str) -> Path:
    target = PACK_DIR / f"{split}.tar"
    if target.exists():
        print(f"[pack] {target.name} already exists, reusing", flush=True)
        return target
    partial = target.with_suffix(".tar.partial")
    count = 0
    with tarfile.open(partial, "w") as archive:
        for kind in ("images", "labels"):
            folder = DATASET / kind / split
            for path in sorted(folder.iterdir()):
                if path.is_file():
                    archive.add(path, arcname=f"{kind}/{split}/{path.name}")
                    count += 1
    partial.rename(target)
    print(f"[pack] {target.name}: {count} files, {target.stat().st_size / 1e9:.2f} GB", flush=True)
    return target


def upload(api: HfApi, repo: str, source: Path, remote_path: str) -> None:
    size = source.stat().st_size
    for entry in api.get_paths_info(repo, [remote_path]):
        if getattr(entry, "size", None) == size:
            print(f"[upload] {remote_path} already on the Hub, skipping", flush=True)
            return
    started = time.time()
    api.upload_file(
        path_or_fileobj=str(source), path_in_repo=remote_path, repo_id=repo,
        commit_message=f"Add {remote_path}",
    )
    # upload_file does not fail when the Hub ignores the path, so check.
    remote = api.get_paths_info(repo, [remote_path])
    if not remote or getattr(remote[0], "size", None) != size:
        raise SystemExit(f"{remote_path} is not on the Hub after upload (ignored by .gitignore?)")
    print(f"[upload] {remote_path}: {size / 1e9:.2f} GB in {time.time() - started:.0f} s", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo")
    parser.add_argument("--with-source-archives", action="store_true",
                        help="also upload the original archives in data/import_data_rar")
    args = parser.parse_args()

    api = HfApi()
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    for name in SMALL_FILES:
        if (DATASET / name).exists():
            upload(api, args.repo, DATASET / name, f"{REMOTE_ROOT}/data_train/{name}")
    for split in SPLITS:
        upload(api, args.repo, pack(split), f"{REMOTE_ROOT}/data_train/{split}.tar")
    if args.with_source_archives:
        archives = sorted(
            path for path in SOURCE_ARCHIVES.iterdir()
            if path.is_file() and path.name.endswith(ARCHIVE_SUFFIXES)
        )
        # Smallest first, so a slow link still delivers most files early.
        for path in sorted(archives, key=lambda item: item.stat().st_size):
            upload(api, args.repo, path, f"{REMOTE_ROOT}/import_data_rar/{path.name}")
    print("ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
