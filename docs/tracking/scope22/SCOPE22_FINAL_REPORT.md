# Scope 22 — Final report

Status: **INT8_PATH_BLOCKED**.

The NCNN PTQ toolchain was successfully built in isolation and created real INT8 artifacts for the three approved shortlist candidates. All artifacts loaded on the host and showed NCNN int8 graph markers. However, the fixed host diagnostic parity gate failed for all three because of detection-count mismatches on the 8-image train-only diagnostic subset:

- YOLOv8n-480 NCNN: 7/8 mismatches.
- YOLOv8n-640 NCNN: 2/8 mismatches.
- YOLOv11n-480 NCNN: 8/8 mismatches.

Therefore no candidate was transferred to Pi, no Pi INT8 benchmark was run, and no INT8 candidate is eligible for freeze review. Scope 21 FP32 NCNN Pi evidence remains the deployment baseline. INT8 artifacts are retained as diagnostic-only Scope 22 outputs.

TEST remains locked, INT8 calibration remains train-only, `SESSION_DISJOINT` remains `UNVERIFIED`, and no production model was frozen.
