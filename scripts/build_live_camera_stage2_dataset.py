#!/usr/bin/env python3
"""Build a close-range USB-camera adaptation dataset in temporary storage.

The dataset keeps every image from ``drone-live-camera-v1`` in TRAIN, adds
deterministic close crops derived only from its ``my_dataset`` TRAIN members,
and oversamples two manually reviewed USB-camera frames.  Frozen V3 TEST is
not read or linked.  The output is diagnostic/adaptation data, not an
independent benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import time
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/processed/drone-live-camera-v1"
V3 = ROOT / "data/processed/drone-single-class-v3-labelrepair-candidate"
DEFAULT_OUTPUT = Path("/tmp/drone-live-camera-stage2")

USB_SEEDS = {
    "usb_fixed": {
        "image": Path("/tmp/pi_camera_fixed_raw.jpg"),
        # Visible drone extent; the object is truncated by bottom/right frame edges.
        "label": "0 0.610938 0.810417 0.778125 0.379167\n",
    },
    "usb_close": {
        "image": Path("/tmp/current_false_raw.jpg"),
        # Visible drone extent; the object is truncated by top/right frame edges.
        "label": "0 0.668750 0.400000 0.662500 0.800000\n",
    },
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


def parse_boxes(label: Path) -> list[tuple[float, float, float, float]]:
    boxes = []
    for row in label.read_text(encoding="utf-8").splitlines():
        fields = row.split()
        if not fields:
            continue
        if len(fields) != 5 or fields[0] != "0":
            raise ValueError(f"Unexpected label in {label}: {row!r}")
        boxes.append(tuple(float(value) for value in fields[1:]))
    return boxes


def close_crop(
    image_path: Path,
    boxes: list[tuple[float, float, float, float]],
    destination_image: Path,
    destination_label: Path,
    rng: random.Random,
) -> bool:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Cannot read {image_path}")
    height, width = image.shape[:2]
    pixel_boxes = [
        (
            (xc - bw / 2) * width,
            (yc - bh / 2) * height,
            (xc + bw / 2) * width,
            (yc + bh / 2) * height,
        )
        for xc, yc, bw, bh in boxes
    ]
    x1 = min(box[0] for box in pixel_boxes)
    y1 = min(box[1] for box in pixel_boxes)
    x2 = max(box[2] for box in pixel_boxes)
    y2 = max(box[3] for box in pixel_boxes)
    box_w, box_h = x2 - x1, y2 - y1

    # Produce a 4:3 crop where the drone occupies 35-78% of the crop.  Center
    # jitter includes realistic partial truncation but retains at least 65% of
    # every source box so the visible-extent annotation remains meaningful.
    target_fraction = rng.uniform(0.35, 0.78)
    crop_w = max(box_w / target_fraction, box_h / target_fraction * 4 / 3)
    crop_w = min(float(width), max(crop_w, 96.0))
    crop_h = min(float(height), crop_w * 3 / 4)
    crop_w = crop_h * 4 / 3
    center_x = (x1 + x2) / 2 + rng.uniform(-0.22, 0.22) * box_w
    center_y = (y1 + y2) / 2 + rng.uniform(-0.22, 0.22) * box_h
    left = int(round(max(0.0, min(width - crop_w, center_x - crop_w / 2))))
    top = int(round(max(0.0, min(height - crop_h, center_y - crop_h / 2))))
    right = int(round(min(width, left + crop_w)))
    bottom = int(round(min(height, top + crop_h)))
    if right - left < 32 or bottom - top < 24:
        return False

    crop = image[top:bottom, left:right]
    crop_h_px, crop_w_px = crop.shape[:2]
    output_rows = []
    for bx1, by1, bx2, by2 in pixel_boxes:
        cx1 = max(0.0, bx1 - left)
        cy1 = max(0.0, by1 - top)
        cx2 = min(float(crop_w_px), bx2 - left)
        cy2 = min(float(crop_h_px), by2 - top)
        original_area = max(1.0, (bx2 - bx1) * (by2 - by1))
        visible_area = max(0.0, cx2 - cx1) * max(0.0, cy2 - cy1)
        if cx2 <= cx1 or cy2 <= cy1 or visible_area / original_area < 0.65:
            continue
        xc = (cx1 + cx2) / 2 / crop_w_px
        yc = (cy1 + cy2) / 2 / crop_h_px
        bw = (cx2 - cx1) / crop_w_px
        bh = (cy2 - cy1) / crop_h_px
        output_rows.append(f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
    if not output_rows:
        return False

    destination_image.parent.mkdir(parents=True, exist_ok=True)
    destination_label.parent.mkdir(parents=True, exist_ok=True)
    resized = cv2.resize(crop, (640, 480), interpolation=cv2.INTER_LINEAR)
    if not cv2.imwrite(str(destination_image), resized, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise OSError(f"Failed to write {destination_image}")
    destination_label.write_text("\n".join(output_rows) + "\n", encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--crops-per-positive", type=int, default=2)
    parser.add_argument("--seed-repeats", type=int, default=256)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")

    image_dir = output / "images/train"
    label_dir = output / "labels/train"
    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    base_images = sorted((BASE / "images/train").iterdir())
    counts = {
        "base_train_images": 0,
        "my_train_images_preserved": 0,
        "generated_close_crops": 0,
        "usb_seed_unique_images": len(USB_SEEDS),
        "usb_seed_repeated_records": 0,
    }

    for image in base_images:
        label = BASE / "labels/train" / f"{image.stem}.txt"
        if not label.is_file():
            raise FileNotFoundError(label)
        link(image, image_dir / image.name)
        link(label, label_dir / f"{image.stem}.txt")
        counts["base_train_images"] += 1
        counts["my_train_images_preserved"] += int(image.name.startswith("my__"))

    rng = random.Random(20260927)
    my_images = [image for image in base_images if image.name.startswith("my__")]
    for image in my_images:
        label = BASE / "labels/train" / f"{image.stem}.txt"
        boxes = parse_boxes(label)
        if not boxes:
            continue
        for index in range(args.crops_per_positive):
            name = f"crop{index}__{image.stem}.jpg"
            if close_crop(
                image,
                boxes,
                image_dir / name,
                label_dir / f"{Path(name).stem}.txt",
                rng,
            ):
                counts["generated_close_crops"] += 1

    for seed_name, record in USB_SEEDS.items():
        image = record["image"]
        if not image.is_file():
            raise FileNotFoundError(image)
        for index in range(args.seed_repeats):
            name = f"seed__{seed_name}__{index:04d}{image.suffix.lower()}"
            link(image, image_dir / name)
            (label_dir / f"{Path(name).stem}.txt").write_text(record["label"], encoding="utf-8")
            counts["usb_seed_repeated_records"] += 1

    data_yaml = output / "data.yaml"
    data_yaml.write_text(
        f"path: {output}\ntrain: images/train\nval: {V3 / 'images/val'}\nnames:\n  0: drone\n",
        encoding="utf-8",
    )
    manifest = {
        "dataset_id": "drone-live-camera-stage2",
        "created_at_unix": time.time(),
        "base_dataset": str(BASE),
        "base_manifest_sha256": sha256(BASE / "build_manifest.json"),
        "policy": "full base TRAIN + my_dataset close crops + reviewed USB seeds",
        "v3_test_accessed": False,
        "seed_source_hashes": {name: sha256(row["image"]) for name, row in USB_SEEDS.items()},
        "seed_labels": {name: row["label"].strip() for name, row in USB_SEEDS.items()},
        "counts": counts,
    }
    manifest_path = output / "build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "SHA256SUMS").write_text(
        f"{sha256(data_yaml)}  data.yaml\n{sha256(manifest_path)}  build_manifest.json\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
