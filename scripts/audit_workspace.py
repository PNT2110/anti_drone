from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def audit_dataset(root: Path) -> None:
    images = [p for p in (root / "images").rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    labels = [p for p in (root / "labels").rglob("*.txt") if p.is_file()]
    image_rel = {p.relative_to(root / "images").with_suffix(".txt") for p in images}
    label_rel = {p.relative_to(root / "labels") for p in labels}
    print(f"DATASET {root} images={len(images)} labels={len(labels)} missing_labels={len(image_rel-label_rel)} orphan_labels={len(label_rel-image_rel)}")
    for split in ("train", "val", "test"):
        split_images = sum(1 for p in (root / "images" / split).rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
        split_labels = sum(1 for p in (root / "labels" / split).rglob("*.txt") if p.is_file())
        print(f"  SPLIT {split} images={split_images} labels={split_labels}")


def audit_artifacts(root: Path) -> None:
    groups = defaultdict(lambda: [0, 0, None, None])
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        group = rel.parts[0] if rel.parts else "."
        stat = p.stat()
        row = groups[group]
        row[0] += 1; row[1] += stat.st_size
        row[2] = max(row[2], stat.st_mtime) if row[2] else stat.st_mtime
        row[3] = min(row[3], stat.st_mtime) if row[3] else stat.st_mtime
    print("ARTIFACT_GROUPS")
    for group, (count, size, newest, oldest) in sorted(groups.items()):
        print(f"  {group}: files={count} bytes={size} newest={newest:.0f} oldest={oldest:.0f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path("data/data_train"))
    ap.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    args = ap.parse_args()
    audit_dataset(args.dataset.resolve())
    audit_artifacts(args.artifacts.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
