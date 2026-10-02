# Scope 21 — Final report

Status: **COMPLETE FOR RESEARCH & DESIGN REVIEW; NOT A PRODUCTION FREEZE**.

Real Pi 5 access, artifact transfer, runtime parity, and the fixed FP32 benchmark protocol all passed. All 10 eligible candidates completed 800 measured inferences each. Overall runner status: `PASS`.

Key evidence:

- Raspberry Pi 5 Model B Rev 1.0, aarch64, 4 GiB RAM.
- Temperature `temp=51.0'C` → `temp=73.0'C`; throttling `throttled=0x0` → `throttled=0x0`.
- All 10 candidates: artifact hash PASS, runtime parity PASS, exact detection counts on 8/8 images.
- FP32 only; INT8 remains Scope 20 `BLOCKED`.
- V3 TEST was not accessed; `SESSION_DISJOINT` and `SPLIT_UNVERIFIED` remain unchanged.
- No retraining, label/split/tracker changes, camera/servo/live targeting, or production freeze.

The first diagnostic run was rejected because the NCNN harness supplied already-normalized float data to an API requiring uint8 input. The harness was corrected to preserve the Scope 20 preprocessing contract, and the full protocol was rerun. The benchmark table and machine artifacts contain only the corrected run.

Reports: [Pi benchmark](SCOPE21_PI_BENCHMARK.md), [Pi parity](SCOPE21_PI_PARITY.md), [selection evidence](SCOPE21_SELECTION_EVIDENCE.md), [transfer](SCOPE21_ARTIFACT_TRANSFER.md).

Machine evidence: `/run/media/pnt/APP/anti_drone/.runtime/scope21`.
