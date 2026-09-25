# Scope 21 — Input audit

Status: **PASS**.

- Scope 20 baseline audit: `PASS`.
- Six Scope 18 `best.pt` hashes: all match.
- Fixed benchmark membership: 8 images from `train`; `test_accessed=false`.
- V3 TEST remains locked.
- Eligible candidates: exactly 10 Scope 20 `PARITY_PASS` pairs.
- YOLO26 NCNN: excluded because Scope 20 marked both pairs `PARITY_FAIL`.

Machine evidence: `.runtime/scope21/input_audit.json` and `.runtime/scope21/scope21_summary.json`.
