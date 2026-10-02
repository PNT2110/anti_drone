# Scope 22 — Host INT8 diagnostic parity

Status: **INT8_RUNTIME_FAIL for all three candidates**.

Acceptance was fixed before inspecting results: detection-count mismatch `= 0`, class mismatch `= 0`, minimum bbox IoU `>= 0.90`, maximum confidence shift `<= 0.20`, over the fixed 8 train images. No threshold was changed after seeing results.

| Candidate | Images | Count mismatch | Class mismatch | Min bbox IoU | Max confidence diff | Status |
|---|---:|---:|---:|---:|---:|---|
| `scope18-yolov8n-480` | 8 | 7 | 0 | 0.548197 | 0.049067 | `INT8_RUNTIME_FAIL` |
| `scope18-yolov8n-640` | 8 | 2 | 0 | 0.682338 | 0.059213 | `INT8_RUNTIME_FAIL` |
| `scope18-yolov11n-480` | 8 | 8 | 0 | 0.618231 | 0.030995 | `INT8_RUNTIME_FAIL` |

The INT8 runtimes loaded and produced the expected NCNN output contract, but detection-count loss makes every candidate ineligible for Pi transfer. Full per-image outputs are in `.runtime/scope22/host_int8_parity.json`.
