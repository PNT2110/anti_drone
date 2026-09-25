# Scope 25 — Freeze manifest

Status: **`FP32_NCNN_CANDIDATE_FROZEN`**.

- Manifest: [`scope25_freeze_manifest.json`](../../../.runtime/scope25/scope25_freeze_manifest.json)
- Manifest SHA-256: `e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964`
- Sidecar: [`scope25_freeze_manifest.sha256`](../../../.runtime/scope25/scope25_freeze_manifest.sha256)
- Candidate: `scope18-yolov8n-480:ncnn`
- Production precision: FP32
- Production backend: NCNN
- TEST accessed: `false`

The manifest binds the production package file hashes, checkpoint/export hashes, contract hashes, dataset/split provenance, and Scope 25R Pi evidence hash. Any model, backend, preprocess, postprocess, or runtime change invalidates this freeze.
