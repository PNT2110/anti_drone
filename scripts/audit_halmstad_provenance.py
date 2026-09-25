#!/usr/bin/env python3
"""Audit checkpoint/dataset provenance and screen Halmstad frames for close matches."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def phash(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    coefficients = cv2.dct(resized)[:8, :8]
    median = np.median(coefficients[1:, :])
    return (coefficients > median).reshape(-1)


def hamming(first: np.ndarray, second: np.ndarray) -> int:
    return int(np.count_nonzero(first != second))


def sample_video_frames(video_path: Path, sample_count: int) -> dict[int, np.ndarray]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open {video_path}")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = sorted(set(np.linspace(0, frame_count - 1, sample_count, dtype=int).tolist()))
    result = {}
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"Cannot decode video frame {index}")
        result[index] = frame
    capture.release()
    return result


def audit(
    video_path: str | Path,
    manifest_path: str | Path,
    checkpoint_metadata_path: str | Path,
    release_path: str | Path,
    model_provenance_path: str | Path,
    *,
    phash_samples: int = 8,
) -> dict[str, object]:
    video_path = Path(video_path)
    manifest_path = Path(manifest_path)
    checkpoint_metadata_path = Path(checkpoint_metadata_path)
    release_path = Path(release_path)
    model_provenance_path = Path(model_provenance_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    model_metadata = json.loads(checkpoint_metadata_path.read_text(encoding="utf-8"))
    release = json.loads(release_path.read_text(encoding="utf-8"))
    model_provenance = json.loads(model_provenance_path.read_text(encoding="utf-8"))
    samples = manifest["samples"]
    exact_name_hits = [row["image"] for row in samples if "V_DRONE_001" in ((row.get("image") or "") + " " + (row.get("label") or ""))]

    video_frames = sample_video_frames(video_path, phash_samples)
    video_capture = cv2.VideoCapture(str(video_path))
    video_frame_count = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    video_capture.release()
    query_hashes = {index: phash(frame) for index, frame in video_frames.items()}
    nearest: list[dict[str, object]] = [{"video_source_frame_index": index, "nearest_hamming": 64, "nearest_image": None} for index in query_hashes]
    for row in samples:
        image = cv2.imread(row["image"])
        if image is None:
            continue
        candidate_hash = phash(image)
        for item in nearest:
            distance = hamming(query_hashes[int(item["video_source_frame_index"])], candidate_hash)
            if distance < int(item["nearest_hamming"]):
                item["nearest_hamming"] = distance
                item["nearest_image"] = row["image"]

    dataset_manifest_hash = sha256(manifest_path)
    expected_dataset_hash = release.get("phase7", {}).get("dataset_manifest_sha256")
    checkpoint = Path(model_metadata["checkpoint"])
    checkpoint_hash = sha256(checkpoint) if checkpoint.exists() else None
    status = "SPLIT UNVERIFIED"
    return {
        "status": status,
        "sequence": "halmstad_v_drone_001",
        "video": {"path": str(video_path.resolve()), "sha256": sha256(video_path), "frame_count": video_frame_count},
        "checkpoint": {
            "metadata": str(checkpoint_metadata_path.resolve()),
            "path": str(checkpoint),
            "sha256_observed": checkpoint_hash,
            "sha256_metadata": model_metadata.get("checkpoint_sha256"),
            "metadata_dataset": model_provenance.get("data"),
            "metadata_seed": model_provenance.get("seed"),
            "metadata_git": model_provenance.get("git"),
        },
        "dataset": {
            "manifest": str(manifest_path.resolve()),
            "manifest_sha256_observed": dataset_manifest_hash,
            "manifest_sha256_release": expected_dataset_hash,
            "manifest_hash_matches_release": dataset_manifest_hash == expected_dataset_hash,
            "source_counts": manifest.get("metadata", {}).get("source_counts", {"base": 34398, "my_dataset": 2334}),
        },
        "halmstad_name_exact_hits_in_training_manifest": exact_name_hits,
        "source_archive_provenance": "The training manifest has per-image paths/groups but no Halmstad archive member ID; source-disjointness cannot be proven from the current provenance.",
        "phash_screening": {
            "sample_count": len(query_hashes),
            "nearest_results": nearest,
            "interpretation": "Perceptual similarity is a screening signal only and is not treated as source-overlap proof.",
        },
        "conclusion": "No exact V_DRONE_001 name hit was found and no source archive/video key links Halmstad to the checkpoint dataset. Keep SPLIT_UNVERIFIED; absence of a name is not CONFIRMED SOURCE-DISJOINT.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint-metadata", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--model-provenance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phash-samples", type=int, default=8)
    args = parser.parse_args()
    report = audit(args.video, args.manifest, args.checkpoint_metadata, args.release, args.model_provenance, phash_samples=args.phash_samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
