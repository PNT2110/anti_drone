# Scope 22 — Input audit

Status: **PASS** for the locked study inputs.

- Approved candidates: exactly 3 NCNN pairs: YOLOv8n-480, YOLOv8n-640, YOLOv11n-480.
- Scope 20 parity: `PARITY_PASS` for all three.
- Scope 21 real Pi evidence: `PI_BENCHMARK_PASS` and Pi parity PASS for all three.
- Scope 19 NCNN hashes: unchanged and matched.
- Calibration: 128 exact `train` images; manifest SHA-256 `4c582deab8ec13a23a0ecf0b1b806e6f3dd0c2c43f5a7dca06c785227e444b59`; `test_accessed=false`.
- Dataset manifest SHA-256: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`.
- YOLO26 NCNN excluded because Scope 20 marked it `PARITY_FAIL`.

The inputs passed audit, but INT8 deployment is blocked by host diagnostic parity.
