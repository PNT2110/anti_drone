#!/usr/bin/env python3
"""Add visually reviewed fresh Pi USB frames to the full stage-2 TRAIN set."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path


DEFAULT_BASE = Path("/tmp/drone-live-camera-stage2")
DEFAULT_FRESH = Path("/tmp/live_v2_fresh_frames")
DEFAULT_OUTPUT = Path("/tmp/drone-live-camera-stage3")
V3_VAL = Path(__file__).resolve().parents[1] / "data/processed/drone-single-class-v3-labelrepair-candidate/images/val"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source.resolve())


def yolo_row(box: list[float], width: int = 640, height: int = 480) -> str:
    x1, y1, x2, y2 = box
    values = ((x1 + x2) / 2 / width, (y1 + y2) / 2 / height, (x2 - x1) / width, (y2 - y1) / height)
    if not all(0.0 <= value <= 1.0 for value in values) or values[2] <= 0 or values[3] <= 0:
        raise ValueError(f"invalid reviewed fresh-frame box: {box}")
    return "0 " + " ".join(f"{value:.6f}" for value in values) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--fresh", type=Path, default=DEFAULT_FRESH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fresh-repeats", type=int, default=48)
    args = parser.parse_args()
    base, fresh, output = args.base.resolve(), args.fresh.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    (output / "images/train").mkdir(parents=True)
    (output / "labels/train").mkdir(parents=True)

    base_images = sorted((base / "images/train").iterdir())
    for image in base_images:
        label = base / "labels/train" / f"{image.stem}.txt"
        if not label.is_file():
            raise FileNotFoundError(label)
        link(image, output / "images/train" / image.name)
        link(label, output / "labels/train" / f"{image.stem}.txt")

    review_records = json.loads((fresh / "auto_labels.json").read_text(encoding="utf-8"))
    accepted = []
    for record in review_records:
        image = Path(record["image"])
        data = image.read_bytes()
        if not data.endswith(b"\xff\xd9"):
            continue
        chosen = record.get("chosen")
        if not chosen:
            continue
        label_row = yolo_row(chosen["bbox"])
        accepted.append(
            {
                "source": str(image),
                "sha256": sha256(image),
                "review": "largest whole-visible-drone box; visually reviewed contact sheet",
                "label": label_row.strip(),
                "source_high_count": len(record.get("detections", [])),
            }
        )
        for index in range(args.fresh_repeats):
            name = f"freshpi__{image.stem}__{index:03d}.jpg"
            link(image, output / "images/train" / name)
            (output / "labels/train" / f"{Path(name).stem}.txt").write_text(label_row, encoding="utf-8")

    data_yaml = output / "data.yaml"
    data_yaml.write_text(
        f"path: {output}\ntrain: images/train\nval: {V3_VAL}\nnames:\n  0: drone\n",
        encoding="utf-8",
    )
    manifest = {
        "dataset_id": "drone-live-camera-stage3",
        "created_at_unix": time.time(),
        "base": str(base),
        "base_manifest_sha256": sha256(base / "build_manifest.json"),
        "base_train_records": len(base_images),
        "fresh_frames_reviewed": len(review_records),
        "fresh_frames_accepted": len(accepted),
        "fresh_frames_rejected_corrupt_or_unlabelled": len(review_records) - len(accepted),
        "fresh_repeats": args.fresh_repeats,
        "fresh_train_records": len(accepted) * args.fresh_repeats,
        "total_train_records": len(base_images) + len(accepted) * args.fresh_repeats,
        "v3_test_accessed": False,
        "fresh_records": accepted,
    }
    manifest_path = output / "build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "fresh_records"}, indent=2))


if __name__ == "__main__":
    main()
