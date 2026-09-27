import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/deploy/live-camera-v2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_live_camera_candidate_is_separate_and_hash_locked():
    manifest = json.loads((ARTIFACT / "model_manifest.json").read_text())
    assert manifest["candidate_id"] == "yolov8n-480-live-camera-stage3-epoch4"
    assert manifest["backend"] == "NCNN"
    assert manifest["precision"] == "FP32"
    assert manifest["imgsz"] == 480
    assert manifest["confidence_threshold"] == 0.25
    assert manifest["nms_iou"] == 0.70
    assert manifest["suppress_contained_duplicates"] is True
    assert manifest["identity_mode"] == "SINGLE_DRONE_SESSION"
    assert manifest["public_target_id"] == 1
    assert sha256(ARTIFACT / "model.ncnn.param") == manifest["ncnn_param_sha256"]
    assert sha256(ARTIFACT / "model.ncnn.bin") == manifest["ncnn_bin_sha256"]
    assert manifest["ncnn_bin_sha256"] != "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def test_all_my_dataset_samples_are_in_training_policy():
    manifest = json.loads((ARTIFACT / "model_manifest.json").read_text())
    counts = manifest["training_counts"]
    assert counts["my_dataset_train"] == 2334
    assert counts["v3_train"] == 12142
    assert counts["fresh_usb_frames"] == 26
    assert counts["total_stage3_train_records"] == (
        counts["v3_train"]
        + counts["my_dataset_train"]
        + counts["generated_close_crops"]
        + counts["stage2_usb_seed_records"]
        + counts["fresh_usb_sampling_records"]
    )
    assert manifest["v3_test_accessed"] is False


def test_runtime_template_points_to_live_camera_candidate():
    config = json.loads((ROOT / "configs/anti_drone_pi_servo.json").read_text())
    manifest = json.loads((ARTIFACT / "model_manifest.json").read_text())
    assert config["model_dir"] == "artifacts/deploy/live-camera-v2"
    assert config["param_sha256"] == manifest["ncnn_param_sha256"]
    assert config["bin_sha256"] == manifest["ncnn_bin_sha256"]
    assert config["tracker_config"]["track_high_thresh"] == 0.25
    assert config["tracker_config"]["track_low_thresh"] == 0.10


def test_scope25_frozen_artifact_remains_unchanged():
    frozen = ROOT / "artifacts/production-candidate/scope25"
    assert sha256(frozen / "model.ncnn.param") == "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
    assert sha256(frozen / "model.ncnn.bin") == "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"
