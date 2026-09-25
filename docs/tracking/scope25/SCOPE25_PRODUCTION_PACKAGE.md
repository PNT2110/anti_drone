# Scope 25 — Production package

Status: **CREATED AND VERIFIED**.

Package: [`artifacts/production-candidate/scope25/`](../../../artifacts/production-candidate/scope25/)

The package was copied from the verified Scope 19 NCNN source; no export was regenerated and no source artifact was moved or overwritten. `SHA256SUMS` verification passed for all package files except the checksum index itself, which is covered by the freeze manifest.

Package contents:

- `model.ncnn.param` — `8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5`
- `model.ncnn.bin` — `23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7`
- `model_manifest.json`
- `preprocess_contract.json`
- `postprocess_contract.json`
- `runtime_contract.json`
- `provenance.json`
- `SHA256SUMS` — `3f1ad7cff8a59f1a5c0b05dca6327a4b11e108f00dbd6c83f5baa4b4306da55f`

The selected candidate is `scope18-yolov8n-480:ncnn`, FP32, 480×480. INT8 remains `PTQ_INT8_PATHS_EXHAUSTED_FOR_CURRENT_SCOPE` and is not part of this package.
