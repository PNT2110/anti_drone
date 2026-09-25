from pathlib import Path

import pytest

from scripts.convert_halmstad_sidecar import convert_source_boxes, inspect_sidecar


SEQUENCE = Path("data/tracking_eval/sequence_001")
SIDECAR = SEQUENCE / "source/V_DRONE_001_LABELS.mat"
MANIFEST = SEQUENCE / "frame_manifest.csv"


def test_matlab_sidecar_parses_real_ground_truth_structure():
    if not SIDECAR.exists() or not MANIFEST.exists():
        pytest.skip("Scope 03 sequence artifact is not available")
    report = inspect_sidecar(SIDECAR)
    assert report["mat_version"].startswith("MATLAB v5")
    assert report["frame_count"] == 301
    assert report["label_definitions"] == ["AIRPLANE", "BIRD", "DRONE", "HELICOPTER"]
    assert report["drone_box_count"] == 301
    assert report["drone_annotated_frames"] == 301
    assert report["multiple_drone_frames"] == 0
    assert report["coordinate_format"] == "xywh_pixels"
    assert report["identity_metadata"] is False


def test_source_box_conversion_preserves_provenance_and_no_track_id(tmp_path):
    if not SIDECAR.exists() or not MANIFEST.exists():
        pytest.skip("Scope 03 sequence artifact is not available")
    output = tmp_path / "source_boxes.csv"
    report = convert_source_boxes(SIDECAR, MANIFEST, output, "halmstad_v_drone_001")
    lines = output.read_text(encoding="utf-8").splitlines()
    assert report["converted_rows"] == 301
    assert "track_id" not in lines[0]
    assert "V_DRONE_001_LABELS.mat:gTruth.LabelData.DRONE[row=0" in lines[1]


def test_source_conversion_rejects_frame_offset(tmp_path):
    if not SIDECAR.exists() or not MANIFEST.exists():
        pytest.skip("Scope 03 sequence artifact is not available")
    bad_manifest = tmp_path / "manifest.csv"
    text = MANIFEST.read_text(encoding="utf-8")
    bad_manifest.write_text(text.replace("halmstad_v_drone_001,1,0,", "halmstad_v_drone_001,2,0,", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="Frame alignment failed"):
        convert_source_boxes(SIDECAR, bad_manifest, tmp_path / "boxes.csv", "halmstad_v_drone_001")
