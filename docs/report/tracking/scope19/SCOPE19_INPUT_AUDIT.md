# Scope 19 — Input audit

Status: **PASS**

The audit locks the six Scope 18 `best.pt` checkpoints, the repaired V3 candidate, and a deterministic train-only benchmark/calibration protocol. `test_accessed=False`. No validation or test inference was rerun.

## Frozen checkpoint hashes

| Run | Actual SHA-256 | Expected Scope 18 SHA-256 | Result |
|---|---|---|---|
| `scope18-yolo26n-480` | `1500fb46bbf01910f85a0b75b37e00f275bf0cb725c0829e7c2db293ea6a23d6` | `1500fb46bbf01910f85a0b75b37e00f275bf0cb725c0829e7c2db293ea6a23d6` | PASS |
| `scope18-yolo26n-640` | `3153d0ffdd6b4db7b3fd28fa4026636fe3ffad19acaedbea1c4f35c996fb8bae` | `3153d0ffdd6b4db7b3fd28fa4026636fe3ffad19acaedbea1c4f35c996fb8bae` | PASS |
| `scope18-yolov11n-480` | `6f086a2206a466c1037e6aab3ddbbf1afc40b38f7643e9be4f83a85630a81e05` | `6f086a2206a466c1037e6aab3ddbbf1afc40b38f7643e9be4f83a85630a81e05` | PASS |
| `scope18-yolov11n-640` | `ab2d146424a2c9c0ce053b122463d7d2e796834e9671a60bdeacd4047ca68186` | `ab2d146424a2c9c0ce053b122463d7d2e796834e9671a60bdeacd4047ca68186` | PASS |
| `scope18-yolov8n-480` | `359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e` | `359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e` | PASS |
| `scope18-yolov8n-640` | `debcef45f0a1667f16c62daf7a8f42d0e5932be498b549b2f985bc72915e9718` | `debcef45f0a1667f16c62daf7a8f42d0e5932be498b549b2f985bc72915e9718` | PASS |

Dataset manifest SHA-256: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`  
Split registry SHA-256: `c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1`  
Scope 18 ledger: `/run/media/pnt/APP/anti_drone/.runtime/scope18/run_ledger.json`  
Benchmark input: `/run/media/pnt/APP/anti_drone/.runtime/scope19/benchmark_input_manifest.json` (8 lexicographically first `train` images)  
INT8 calibration manifest: `/run/media/pnt/APP/anti_drone/.runtime/scope19/calibration_manifest.json` (128 `train` images)

V3 test remains locked. Scope 18 status and frozen validation values are consumed from the ledger only.
