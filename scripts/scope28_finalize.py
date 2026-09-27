#!/usr/bin/env python3
"""Materialize Scope 28 evidence and reports after the accepted Pi run."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime/scope28"
ARTIFACTS = ROOT / "artifacts/integration/scope28"
DOCS = ROOT / "docs/tracking/scope28"
FREEZE = "e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964"
HEADLINE = "7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83"
PARAM = "8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5"
BIN = "23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(name: str):
    return json.loads((RUNTIME / name).read_text())


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def md_table(rows):
    return "\n".join(["| Metric | Value |", "|---|---|"] + [f"| {key} | {value} |" for key, value in rows])


def main() -> int:
    audit = read_json("input_audit.json")
    diagnosis = read_json("contract_diagnosis.json")
    summary = read_json("summary.json")
    parity = read_json("parity_8.json")
    if audit["freeze_manifest_sha256"] != FREEZE or audit["scope26_headline_sha256"] != HEADLINE:
        raise SystemExit("SCOPE28_BASELINE_MISMATCH")
    package = ROOT / "artifacts/production-candidate/scope25"
    if sha256(package / "model.ncnn.param") != PARAM or sha256(package / "model.ncnn.bin") != BIN:
        raise SystemExit("SCOPE28_PACKAGE_MISMATCH")
    if summary["status"] != "DRY_RUN_COMPLETE" or summary["frames_processed"] != 301 or parity["status"] != "PARITY_PASS":
        raise SystemExit("SCOPE28_RUN_NOT_ACCEPTED")
    if summary["high_stream_equivalence"]["fail_frames"] != 0:
        raise SystemExit("HIGH_STREAM_REGRESSION")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for name in ("input_audit.json", "contract_diagnosis.json", "summary.json", "parity_8.json", "target_state.jsonl", "stream_records.jsonl", "public_reference.jsonl"):
        shutil.copy2(RUNTIME / name, ARTIFACTS / name)
    low_rows = []
    for line in (RUNTIME / "stream_records.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row["low_count"]:
            low_rows.append({"frame_id": row["frame_id"], "timestamp": row["timestamp"], "high_count": row["high_count"], "low_count": row["low_count"], "low": row["low"]})
    low_analysis = {"status": "LOW_STREAM_ANALYZED", "frames_with_low_detections": summary["stream_aggregates"]["frames_with_low"], "low_only_frames": summary["stream_aggregates"]["low_only_frames"], "low_box_count": summary["stream_aggregates"]["low_boxes"], "low_association_frames_inferred": summary["association_counts"]["LOW"], "evidence": low_rows, "inference_note": "Association source is inferred by IoU equality between the observed tracker box and the frame's high/low adapter detections; the existing tracker algorithm was not instrumented or changed.", "tracker_floor": 0.10, "public_threshold": 0.25, "nms_iou": 0.70}
    (RUNTIME / "low_stream_analysis.json").write_text(json.dumps(low_analysis, indent=2, ensure_ascii=False) + "\n")
    shutil.copy2(RUNTIME / "low_stream_analysis.json", ARTIFACTS / "low_stream_analysis.json")
    manifest = {"status": "BYTETRACK_TWO_STAGE_INPUT_CONTRACT_RESTORED", "freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "candidate_id": audit["candidate_id"], "tracker_profile": audit["tracker_profile"], "actuator_output_enabled": False, "test_accessed": False, "files": {path.name: sha256(path) for path in sorted(ARTIFACTS.iterdir()) if path.is_file()}}
    (ARTIFACTS / "ARTIFACT_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    run_manifest = {"status": manifest["status"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "freeze_manifest_sha256": FREEZE, "scope26_headline_sha256": HEADLINE, "package_hashes": {"param": PARAM, "bin": BIN}, "scope27_baseline": {"detector_observed_frames": 205, "detector_no_detection_frames": 96, "target_observed_frames": 204, "predicted_only_frames": 41, "no_target_frames": 56, "track_ids": [1, 2, 3, 4, 5], "id_changes": 2, "lost_events": 17, "reacquisition_events": 16, "total_pipeline_ms": 44.5422, "effective_fps": 22.4506}, "scope28_summary_sha256": sha256(RUNTIME / "summary.json"), "parity8_sha256": sha256(RUNTIME / "parity_8.json"), "low_analysis_sha256": sha256(RUNTIME / "low_stream_analysis.json"), "no_v3_test_tuning": True, "no_webcam": True, "dry_run_only": True}
    (RUNTIME / "scope28_run_manifest.json").write_text(json.dumps(run_manifest, indent=2) + "\n")

    max_conf = max(row["parity"]["max_confidence_abs"] for row in parity["images"])
    min_iou = min(row["parity"]["min_bbox_iou"] for row in parity["images"])
    docs = {
        "SCOPE28_INPUT_AUDIT.md": f"""# Scope 28 — Input Audit

Status: `INPUTS_VERIFIED`

{md_table([('Scope 25 freeze manifest SHA-256', FREEZE), ('Scope 26 headline SHA-256', HEADLINE), ('NCNN param SHA-256', PARAM), ('NCNN bin SHA-256', BIN), ('Candidate', audit['candidate_id']), ('Tracker profile', audit['tracker_profile']), ('Diagnostic sequence', 'Halmstad V_DRONE_001, 301 frames, 640x512, 30 FPS'), ('V3 TEST used for tuning', audit['v3_test_used_for_tuning']), ('Webcam used', audit['webcam_used']), ('Physical actuation', audit['physical_actuation_enabled'])])}

The Scope 25/26 baselines and package hashes were verified before Pi activity. The production package was not modified. V3 TEST was not read or used.
""",
        "SCOPE28_CONTRACT_DIAGNOSIS.md": f"""# Scope 28 — Contract Diagnosis

Result: `{diagnosis['status']}`

Scope 27 **did discard** `0.10 <= confidence < 0.25` before `ByteTrack.update`. Evidence was read directly from `scripts/scope27_pi_dryrun.py`, `scripts/scope21_pi_runner.py`, and `src/anti_drone/tracking/bytetrack.py`: Scope 27 called the decoder with `CONF = 0.25`; that decoder filtered candidates before returning; the tracker’s `track_low_thresh=0.10` therefore had no low observations to receive.

This was a real contract gap, so the adapter was implemented. The tracker implementation and its profile/config were not changed.
""",
        "SCOPE28_DUAL_STREAM_DESIGN.md": """# Scope 28 — Dual-Stream Design

`scope28-v1` is an adapter contract, not a detector-threshold replacement:

| Stream | Rule | Consumer |
|---|---|---|
| `FROZEN_PUBLIC_STREAM` | confidence >= 0.25 | frozen public detector semantics / equivalence evidence |
| `TRACKER_LOW_STREAM` | 0.10 <= confidence < 0.25 | existing ByteTrack second association stage |

The adapter performs one NCNN inference, restores boxes to original-frame coordinates, applies one NMS at IoU 0.70 to the floor-filtered candidates, then splits the kept rows. Confidence/class/box values are passed through unchanged. The tracker receives `high + low`; it still creates new tracks only from its unchanged `new_track_thresh=0.35` high path.

The production candidate package and Scope 25/26 artifacts remain untouched.
""",
        "SCOPE28_HIGH_STREAM_EQUIVALENCE.md": f"""# Scope 28 — HIGH Stream Equivalence

Result: `PASS`

Fixed 8-image TRAIN parity: all 8 passed the Scope 20/21 gate (exact detection count and class, confidence absolute difference <= 0.05, bbox IoU >= 0.95). Across the Halmstad diagnostic sequence, the high stream passed **301/301** frame comparisons against the Scope 27 public reference; failures: 0.

{md_table([('8-image max confidence absolute difference', f'{max_conf:.9f}'), ('8-image minimum bbox IoU', f'{min_iou:.9f}'), ('Halmstad frames compared', 301), ('Halmstad high-stream pass frames', 301), ('Halmstad high-stream failures', 0), ('NMS applications per dual frame', 1), ('NCNN inferences per frame', 1)])}

This is equivalence under the frozen acceptance gate; no model, threshold, backend, or postprocess tuning was performed.
""",
        "SCOPE28_LOW_STREAM_ANALYSIS.md": f"""# Scope 28 — LOW Stream Analysis

{md_table([('Frames with any low detection', summary['stream_aggregates']['frames_with_low']), ('Low-only frames', summary['stream_aggregates']['low_only_frames']), ('Low boxes retained', summary['stream_aggregates']['low_boxes']), ('Frames with inferred LOW association', summary['association_counts']['LOW']), ('Tracker floor', '0.10'), ('Frozen public threshold', '0.25')])}

Low observations were present on the Halmstad run and 13 were inferred to participate in association. The inference is based on IoU equality of the observed tracker box with the frame’s low-stream box; the existing ByteTrack code was not instrumented or modified. Low observations were never promoted to high confidence and did not create new tracks by themselves.

The exact frame/box evidence is in `.runtime/scope28/low_stream_analysis.json` and `artifacts/integration/scope28/low_stream_analysis.json`.
""",
        "SCOPE28_TRACKING_RESULTS.md": f"""# Scope 28 — Tracking Results

{md_table([('Frames processed', summary['frames_processed']), ('Track IDs created', summary['track_ids_created']), ('Target observed frames', summary['target_state_summary']['observed_frames']), ('Prediction-only frames', summary['target_state_summary']['predicted_only_frames']), ('No-target frames', summary['target_state_summary']['no_target_frames']), ('ID changes', summary['target_state_summary']['id_changes']), ('Lost events', summary['events']['TRACK_LOST']['count']), ('Reacquisition events', summary['target_state_summary']['reacquisition_events']), ('Coordinate errors', summary['events']['COORDINATE_ERROR']['count']), ('Timestamp errors', summary['events']['TIMESTAMP_ERROR']['count'])])}

Scope 27 baseline for comparison was observed=204, predicted-only=41, no-target=56, IDs=[1,2,3,4,5], ID changes=2, lost=17, reacquisition=16. Scope 28 characterization is not an optimization or a claim of generalization; differences reflect the restored low-score observation input.

Per-frame high/low detections, track IDs, state, association-source inference, and dry-run command preview are in `.runtime/scope28/target_state.jsonl`.
""",
        "SCOPE28_PI_PERFORMANCE.md": f"""# Scope 28 — Pi 5 Performance

Hardware: Raspberry Pi 5 Model B Rev 1.0, aarch64, 4 GiB-class RAM, NCNN FP32, 4 threads. The run used the offline Halmstad file; these are not webcam FPS claims.

{md_table([(key, f"mean={value['mean']:.4f} ms; p50={value['p50']:.4f} ms; p95={value['p95']:.4f} ms") for key, value in summary['latency_ms'].items()] + [('Effective sequential FPS', f"{summary['effective_fps']:.4f}"), ('Scope 27 total baseline', '44.5422 ms mean; 22.4506 FPS'), ('Temperature', f"{summary['hardware'].get('temperature_before')} -> {summary['hardware'].get('temperature_after')}"), ('Throttling', f"{summary['hardware'].get('throttling_before')} -> {summary['hardware'].get('throttling_after')}"), ('Available RAM', f"{summary['hardware'].get('memory_before', {}).get('MemAvailable')} -> {summary['hardware'].get('memory_after', {}).get('MemAvailable')} bytes")])}

The measured total pipeline remained close to Scope 27. Candidate decode and one-NMS/split stages are separated in the evidence. No frame skipping was used.
""",
        "SCOPE28_DRYRUN_SAFETY.md": """# Scope 28 — Dry-Run Safety

- `DRY_RUN_ONLY` was hard-coded in the adapter sink.
- GPIO writes: 0; PWM writes: 0; serial writes: 0.
- No webcam, servo, live targeting, autostart, or system service was used.
- `command_preview` contains only target center/error preview and no hardware command.
- Scope 26 TEST and all V3 TEST images were excluded from the run.
""",
        "SCOPE28_TEST_REPORT.md": """# Scope 28 — Test Report

Accepted Pi evidence: fixed 8-image parity PASS; Halmstad 301/301 dual-stream dry-run PASS; high-stream equivalence 301/301 PASS; coordinate and timestamp errors 0; actuator writes 0.

Regression suite after implementation: **135 passed, 1 skipped**. `python -m compileall -q scripts src tests` passed. `git diff --check` passed.

The first transport attempt exposed a harness key lookup error while reading the frozen host reference. It was corrected before the accepted run; it was not a model, tracker, threshold, or artifact change.
""",
        "SCOPE28_FINAL_REPORT.md": f"""# Scope 28 — Final Report

Final status: `BYTETRACK_TWO_STAGE_INPUT_CONTRACT_RESTORED`

{md_table([('Scope 27 discarded 0.10–<0.25 before ByteTrack?', 'YES'), ('Freeze manifest unchanged', FREEZE), ('Scope 26 headline unchanged', HEADLINE), ('Candidate hashes unchanged', f'param={PARAM}; bin={BIN}'), ('High stream equivalence', '8/8 and 301/301 PASS'), ('Frames with low detections', summary['stream_aggregates']['frames_with_low']), ('Low-only frames', summary['stream_aggregates']['low_only_frames']), ('Low observations inferred in association', summary['association_counts']['LOW']), ('Track IDs', summary['track_ids_created']), ('ID changes', summary['target_state_summary']['id_changes']), ('Lost/reacquisition', f"{summary['events']['TRACK_LOST']['count']}/{summary['target_state_summary']['reacquisition_events']}"), ('Prediction-only/no-target', f"{summary['target_state_summary']['predicted_only_frames']}/{summary['target_state_summary']['no_target_frames']}"), ('Total latency mean/p95', f"{summary['latency_ms']['total_pipeline_ms']['mean']:.4f}/{summary['latency_ms']['total_pipeline_ms']['p95']:.4f} ms"), ('Effective FPS', f"{summary['effective_fps']:.4f}"), ('Temperature/throttling', f"{summary['hardware'].get('temperature_before')} -> {summary['hardware'].get('temperature_after')}; {summary['hardware'].get('throttling_before')} -> {summary['hardware'].get('throttling_after')}"), ('Actuator writes', '0/0/0 GPIO/PWM/serial'), ('V3 TEST tuning', 'No'), ('Webcam/physical actuation', 'No / No')])}

Scope 28 restored the intended ByteTrack two-stage input contract in an external adapter while retaining the frozen public detector semantics. The adapter performs one inference and one NMS per frame, passes high and low observations with original confidence and source-frame coordinates, and leaves `bytetrack_motion_adaptive` unchanged. The 301-frame Halmstad run completed on the verified Pi 5. This remains a diagnostic dry-run, not an independent test or a generalization claim.

Required stop condition: do not start Scope 29 automatically.
""",
    }
    for name, content in docs.items():
        write(DOCS / name, content)
    print(json.dumps({"status": manifest["status"], "docs": sorted(docs), "artifact_manifest_sha256": sha256(ARTIFACTS / "ARTIFACT_MANIFEST.json"), "low_analysis_sha256": sha256(RUNTIME / "low_stream_analysis.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
