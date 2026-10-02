# Scope 20 — Input audit

Status: **PASS**. The final audit was rerun after all corrective work; `errors=0` and `test_accessed=False`.

| Scope 18 run | best.pt SHA-256 | Result |
|---|---|---|
| `scope18-yolo26n-480` | `1500fb46bbf01910f85a0b75b37e00f275bf0cb725c0829e7c2db293ea6a23d6` | PASS |
| `scope18-yolo26n-640` | `3153d0ffdd6b4db7b3fd28fa4026636fe3ffad19acaedbea1c4f35c996fb8bae` | PASS |
| `scope18-yolov11n-480` | `6f086a2206a466c1037e6aab3ddbbf1afc40b38f7643e9be4f83a85630a81e05` | PASS |
| `scope18-yolov11n-640` | `ab2d146424a2c9c0ce053b122463d7d2e796834e9671a60bdeacd4047ca68186` | PASS |
| `scope18-yolov8n-480` | `359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e` | PASS |
| `scope18-yolov8n-640` | `debcef45f0a1667f16c62daf7a8f42d0e5932be498b549b2f985bc72915e9718` | PASS |

Locked V3 manifest: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`  
Locked V3 split registry: `c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1`  
Scope 19 benchmark input: `/run/media/pnt/APP/anti_drone/.runtime/scope19/benchmark_input_manifest.json` (8 train images)  
Scope 19 calibration input: `/run/media/pnt/APP/anti_drone/.runtime/scope19/calibration_manifest.json` (128 train images)  
Scope 19 FP32 ONNX/NCNN artifacts: 12/12 hashes match their Scope 19 ledger.

No `last.pt`, test inference, test scoring, retraining, dataset change, tracker/gate change, or Scope 19 export overwrite is accepted by this scope.
