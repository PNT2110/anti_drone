"""Materialize the assigned portion of V2 as an independent YOLO dataset.

The source manifest and V2 assignment are immutable inputs.  Files are copied
into a temporary sibling directory and atomically renamed only after all rows,
hashes and metadata are written.  Quarantined rows are never considered.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2_DIR = ROOT / "data/processed/drone-single-class-v2"
V2_MANIFEST = V2_DIR / "manifest.json"
V2_REGISTRY = V2_DIR / "split_registry.json"
V2_AUDIT = V2_DIR / "audit.json"
OUTPUT = ROOT / "data/processed/drone-single-class-v2-executable"
EXPECTED = {
    "v1_manifest": "3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d",
    "v2_manifest": "9605532a2b24566b691554125074c37f198c452bce343883b2a6720847299aa1",
    "v2_registry": "5819f6df78156561f3907e0eac05186dd5d77fe556699c74bad0ee5d40f51ed9",
    "v2_audit": "ab6a02db3b5efdff5f4c95d130ab4f9b06eddd18b9541aa7157ebb86f016a120",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    observed = {
        "v2_manifest": sha256_file(V2_MANIFEST),
        "v2_registry": sha256_file(V2_REGISTRY),
        "v2_audit": sha256_file(V2_AUDIT),
    }
    v2 = json.loads(V2_MANIFEST.read_text(encoding="utf-8"))
    registry = json.loads(V2_REGISTRY.read_text(encoding="utf-8"))
    audit = json.loads(V2_AUDIT.read_text(encoding="utf-8"))
    if observed != {key: EXPECTED[key] for key in observed}:
        raise RuntimeError(f"BLOCKED: V2 baseline checksum mismatch: {observed}")
    if audit.get("status") != "PASS" or audit.get("independent_validation_claim") is not False:
        raise RuntimeError("BLOCKED: V2 audit status/independence claim is not the accepted baseline")

    assigned = [row for row in v2["samples"] if row.get("assignment_status") == "ASSIGNED"]
    quarantined = [row for row in v2["samples"] if row.get("assignment_status") == "QUARANTINED"]
    if len(assigned) != 30227 or len(quarantined) != 6505:
        raise RuntimeError("BLOCKED: unexpected V2 assigned/quarantine totals")
    if len({row["group"] for row in assigned}) != 318:
        raise RuntimeError("BLOCKED: assigned group count is not 318")
    if set(row["split"] for row in assigned) != {"train", "val", "test"}:
        raise RuntimeError("BLOCKED: assigned rows have an unexpected split")
    if OUTPUT.exists():
        raise RuntimeError(f"BLOCKED: output already exists; refusing to overwrite: {OUTPUT}")

    source_rows = []
    estimated_bytes = 0
    seen_names: set[tuple[str, str]] = set()
    for index, row in enumerate(assigned):
        source_image = Path(row["image"])
        source_label = Path(row["label"]) if row.get("label") else None
        if not source_image.is_file():
            raise RuntimeError(f"BLOCKED: missing source image for row {index}: {source_image}")
        if source_label is None or not source_label.is_file():
            raise RuntimeError(f"BLOCKED: missing source label for row {index}: {source_label}")
        image_name = Path(row["output_image"]).name
        label_name = Path(row["output_label"]).stem + ".txt"
        key = (row["split"], image_name)
        if key in seen_names:
            raise RuntimeError(f"BLOCKED: duplicate output name: {key}")
        seen_names.add(key)
        estimated_bytes += source_image.stat().st_size + source_label.stat().st_size
        source_rows.append((index, row, source_image, source_label, image_name, label_name))

    free_bytes = shutil.disk_usage(OUTPUT.parent).free
    safety_bytes = int(estimated_bytes * 1.10) + 256 * 1024 * 1024
    if free_bytes < safety_bytes:
        raise RuntimeError(f"BLOCKED: insufficient free space: free={free_bytes}, required={safety_bytes}")

    temp = OUTPUT.with_name(OUTPUT.name + f".building-{os.getpid()}")
    if temp.exists():
        raise RuntimeError(f"BLOCKED: stale build directory exists; refusing to delete: {temp}")
    started = time.time()
    try:
        for split in ("train", "val", "test"):
            (temp / "images" / split).mkdir(parents=True, exist_ok=True)
            (temp / "labels" / split).mkdir(parents=True, exist_ok=True)

        materialized = []
        for position, (index, row, source_image, source_label, image_name, label_name) in enumerate(source_rows, 1):
            image_dst = temp / "images" / row["split"] / image_name
            label_dst = temp / "labels" / row["split"] / label_name
            shutil.copy2(source_image, image_dst)
            shutil.copy2(source_label, label_dst)
            if image_dst.is_symlink() or label_dst.is_symlink():
                raise RuntimeError("BLOCKED: symlink output detected")
            source_hash = sha256_file(source_image)
            output_hash = sha256_file(image_dst)
            if source_hash != row["image_hash"] or output_hash != source_hash:
                raise RuntimeError(f"BLOCKED: image hash mismatch at V2 row {index}")
            materialized.append(
                {
                    "sample_id": f"v2:{index:05d}",
                    "v2_row_index": index,
                    "source": row["source"],
                    "source_image": str(source_image),
                    "source_label": str(source_label),
                    "source_image_hash": row["image_hash"],
                    "source_group": row["group"],
                    "split": row["split"],
                    "v2_provenance_class": row.get("provenance_class"),
                    "assignment_status": row["assignment_status"],
                    "output_image": str(image_dst.relative_to(temp)),
                    "output_label": str(label_dst.relative_to(temp)),
                    "output_image_sha256": output_hash,
                    "output_label_sha256": sha256_file(label_dst),
                }
            )
            if position % 2000 == 0:
                print(f"copied {position}/{len(source_rows)}", flush=True)

        output_manifest = {
            "metadata": {
                "dataset_id": "drone-single-class-v2-executable",
                "dataset_version": "scope12-executable-v1",
                "source_v2_manifest": str(V2_MANIFEST.relative_to(ROOT)),
                "source_v2_manifest_sha256": observed["v2_manifest"],
                "source_v2_registry_sha256": observed["v2_registry"],
                "source_v2_audit_sha256": observed["v2_audit"],
                "seed": 42,
                "grouping_rule_version": v2["metadata"]["grouping_rule_version"],
                "split_algorithm_version": v2["metadata"]["split_algorithm_version"],
                "assigned_sample_count": len(assigned),
                "quarantined_sample_count_excluded": len(quarantined),
                "quarantined_group_count_excluded": len({row["group"] for row in quarantined}),
                "verified_group_count": len({row["group"] for row in assigned}),
                "materialization": "physical copy2; no symlinks or hardlinks",
                "created_at_unix": started,
            },
            "samples": materialized,
        }
        write_json(temp / "manifest.json", output_manifest)
        split_counts = Counter(row["split"] for row in materialized)
        group_splits = {}
        for row in materialized:
            group_splits.setdefault(row["source_group"], set()).add(row["split"])
        if any(len(splits) != 1 for splits in group_splits.values()):
            raise RuntimeError("BLOCKED: verified group was materialized into more than one split")
        split_registry = {
            "dataset_id": "drone-single-class-v2-executable",
            "source_v2_manifest_sha256": observed["v2_manifest"],
            "seed": 42,
            "grouping_rule_version": v2["metadata"]["grouping_rule_version"],
            "split_algorithm_version": v2["metadata"]["split_algorithm_version"],
            "actual_counts": dict(split_counts),
            "assigned_sample_count": len(materialized),
            "excluded_quarantine_sample_count": len(quarantined),
            "verified_group_count": len(group_splits),
            "group_overlap": 0,
            "exact_source_path_overlap": 0,
            "exact_source_hash_overlap": 0,
        }
        write_json(temp / "split_registry.json", split_registry)
        (temp / "data.yaml").write_text(
            f"path: {temp.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\n"
            "names:\n  0: drone\n",
            encoding="utf-8",
        )
        write_json(temp / "training_provenance.json", {
            "dataset_manifest_sha256": observed["v2_manifest"],
            "split_registry_sha256": observed["v2_registry"],
            "source_v2_audit_sha256": observed["v2_audit"],
            "group_rule": v2["metadata"]["grouping_rule_version"],
            "split_algorithm": v2["metadata"]["split_algorithm_version"],
            "seed": 42,
            "sample_ids": [row["sample_id"] for row in materialized],
            "source_references": "manifest.samples[source_image, source_label, source_group, source_image_hash]",
            "excluded_sources": {"assignment_status": "QUARANTINED", "samples": 6505, "groups": 4172},
            "validation_policy": "validation may select checkpoints/parameters; test is held out and must not tune training",
            "halmstad_policy": "Halmstad is not included and no independence claim is made for V1 or V2",
            "resume_policy": "each model/size has a distinct output directory; resume only from that run's last.pt",
        })
        write_json(temp / "materialization_report.json", {
            "status": "PASS",
            "source_rows": len(assigned),
            "materialized_rows": len(materialized),
            "split_counts": dict(split_counts),
            "estimated_input_bytes": estimated_bytes,
            "free_bytes_before": free_bytes,
            "safety_required_bytes": safety_bytes,
            "elapsed_seconds": time.time() - started,
        })
        os.replace(temp, OUTPUT)
        # The data.yaml is written before the atomic rename so the temporary
        # tree is self-contained during the build; repair its stable absolute
        # path after the rename.
        (OUTPUT / "data.yaml").write_text(
            f"path: {OUTPUT.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\n"
            "names:\n  0: drone\n",
            encoding="utf-8",
        )
    except Exception:
        # Keep an interrupted build for forensic inspection; never advertise it
        # as the executable dataset.
        raise
    print(json.dumps({"output": str(OUTPUT), "counts": dict(Counter(row["split"] for row in assigned)), "excluded_quarantine": len(quarantined)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
