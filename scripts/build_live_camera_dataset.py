#!/usr/bin/env python3
"""Build a train-only live-camera adaptation dataset.

The frozen V3 dataset is never modified.  This builder links its TRAIN split
and adds every previously quarantined ``my_dataset`` image, whose labels use
class 15 for drone.  Those labels are copied with class 0.  Seven missing
annotation files are repaired from their adjacent frames (four interpolated
drone boxes and three verified empty frames); intentional empty labels are
retained as hard negatives.  All ``my_dataset`` images belong to TRAIN as the
user requested.  Frozen V3 VAL is used only for training diagnostics.  V3
TEST is never inspected or linked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
V1_MANIFEST = ROOT / "data/processed/drone-single-class/manifest.json"
DEFAULT_OUTPUT = ROOT / "data/processed/drone-live-camera-v1"

# Missing source sidecars. Positive boxes are linear interpolations of the
# immediately adjacent annotated frames; empty entries were visually checked
# and contain no drone. Coordinates remain normalized YOLO xc,yc,w,h.
MISSING_LABEL_REPAIRS = {
    "0124": ["0 0.501171 0.485417 0.077284 0.133334"],
    "0548": ["0 0.712110 0.232986 0.300782 0.322917"],
    "1005": [],
    "1095": ["0 0.489237 0.412696 0.338195 0.133985"],
    "1182": [],
    "1275": [],
    "1689": ["0 0.571528 0.498242 0.437500 0.188672"],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source.resolve())


def remap_label(source: Path, destination: Path) -> tuple[int, bool]:
    rows: list[str] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 5 or fields[0] != "15":
            raise ValueError(f"Unexpected my_dataset label row in {source}: {line!r}")
        coords = [float(value) for value in fields[1:]]
        if not all(0.0 <= value <= 1.0 for value in coords) or coords[2] <= 0 or coords[3] <= 0:
            raise ValueError(f"Invalid normalized box in {source}: {line!r}")
        rows.append("0 " + " ".join(fields[1:]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(("\n".join(rows) + "\n") if rows else "", encoding="utf-8")
    return len(rows), not rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing dataset: {output}")

    for split in ("train",):
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)

    counts = {
        "v3_train_images": 0,
        "my_train_images": 0,
        "my_train_boxes": 0,
        "my_train_negatives": 0,
        "my_missing_label_repaired": 0,
        "my_exact_duplicates_excluded": 0,
    }

    # Preserve the far/small-drone capability using only the frozen TRAIN split.
    for image in sorted((V3 / "images/train").iterdir()):
        if not image.is_file():
            continue
        label = V3 / "labels/train" / f"{image.stem}.txt"
        if not label.is_file():
            raise FileNotFoundError(label)
        name = f"v3__{image.name}"
        link(image, output / "images/train" / name)
        link(label, output / "labels/train" / f"{Path(name).stem}.txt")
        counts["v3_train_images"] += 1

    manifest = json.loads(V1_MANIFEST.read_text(encoding="utf-8"))
    seen_hashes: set[str] = set()
    split_records: list[dict] = []
    for sample in manifest["samples"]:
        if sample.get("source") != "my_dataset":
            continue
        image = Path(sample["image"])
        label_value = sample.get("label")
        label = Path(label_value) if label_value else None
        repair_rows = MISSING_LABEL_REPAIRS.get(image.stem)
        if label is None or not label.is_file():
            if repair_rows is None:
                raise FileNotFoundError(f"Unreviewed missing my_dataset label: {image}")
            counts["my_missing_label_repaired"] += 1
        image_hash = sample["image_hash"]
        if image_hash in seen_hashes:
            counts["my_exact_duplicates_excluded"] += 1
            continue
        seen_hashes.add(image_hash)

        try:
            numeric_id = int(image.stem)
        except ValueError as exc:
            raise ValueError(f"Expected numeric my_dataset filename: {image}") from exc
        block = (numeric_id - 1) // 100
        split = "train"
        name = f"my__{image.name}"
        link(image, output / "images" / split / name)
        destination_label = output / "labels" / split / f"{Path(name).stem}.txt"
        if repair_rows is not None:
            destination_label.write_text(
                ("\n".join(repair_rows) + "\n") if repair_rows else "", encoding="utf-8"
            )
            box_count, is_negative = len(repair_rows), not repair_rows
        else:
            box_count, is_negative = remap_label(label, destination_label)
        counts[f"my_{split}_images"] += 1
        counts[f"my_{split}_boxes"] += box_count
        counts[f"my_{split}_negatives"] += int(is_negative)
        split_records.append(
            {
                "image": str(image),
                "image_sha256": image_hash,
                "source_label": str(label) if label and label.is_file() else None,
                "source_label_sha256": sha256(label) if label and label.is_file() else None,
                "label_repair": repair_rows,
                "split": split,
                "block": block,
                "box_count": box_count,
                "negative": is_negative,
            }
        )

    data_yaml = output / "data.yaml"
    data_yaml.write_text(
        f"path: {output}\n"
        "train: images/train\n"
        f"val: {V3 / 'images/val'}\n"
        "names:\n"
        "  0: drone\n",
        encoding="utf-8",
    )
    build_manifest = {
        "dataset_id": "drone-live-camera-v1",
        "created_at_unix": time.time(),
        "purpose": "live USB-camera adaptation; not an independent benchmark",
        "v3_test_accessed": False,
        "v3_train_source": str(V3 / "images/train"),
        "v3_manifest_sha256": sha256(V3 / "manifest.json"),
        "my_dataset_provenance": "UNRESOLVED; permitted here only as train/diagnostic data",
        "my_class_remap": {"15": 0},
        "my_split_policy": "all my_dataset images in TRAIN per user instruction",
        "validation_policy": "frozen V3 VAL only; live USB frames are separate external diagnostics",
        "counts": counts,
        "my_samples": split_records,
    }
    manifest_path = output / "build_manifest.json"
    manifest_path.write_text(json.dumps(build_manifest, indent=2) + "\n", encoding="utf-8")
    (output / "SHA256SUMS").write_text(
        f"{sha256(data_yaml)}  data.yaml\n{sha256(manifest_path)}  build_manifest.json\n",
        encoding="utf-8",
    )
    print(json.dumps(build_manifest["counts"], indent=2))


if __name__ == "__main__":
    main()
