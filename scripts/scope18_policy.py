"""Pure policy guards used by Scope 18 tests and the training runner."""

from __future__ import annotations


def validate_resume(requested: dict, checkpoint: dict) -> tuple[bool, str]:
    if requested.get("checkpoint_kind") == "best.pt":
        return False, "best.pt is not a resumable training checkpoint"
    fields = ("run_id", "model_id", "imgsz", "dataset_manifest_sha256", "dataset_split_registry_sha256", "seed", "effective_batch")
    for field in fields:
        if requested.get(field) != checkpoint.get(field):
            return False, f"resume mismatch: {field}"
    return True, "resume contract matched"


def training_data_policy() -> dict:
    return {"allowed_splits": ["train", "val"], "test_allowed": False, "test_selection": False, "test_scoring": False}


def output_is_safe(output_root: str, scope15_root: str, scope16_root: str) -> bool:
    return output_root not in {scope15_root, scope16_root} and output_root.endswith("scope18-v3-labelrepair")
