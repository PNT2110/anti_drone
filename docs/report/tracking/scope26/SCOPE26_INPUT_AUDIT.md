# Scope 26 — Input audit

Status: **PASS; first V3 TEST access authorized and recorded**.

- Freeze manifest SHA-256: `e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964`; expected match: PASS.
- Candidate: `scope18-yolov8n-480:ncnn`.
- Package NCNN param/bin hashes: exact match.
- Dataset manifest SHA-256: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`; expected match: PASS.
- Split registry SHA-256: `c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1`; expected match: PASS.
- Locked split counts: train `12142`, val `8237`, test `9848`.
- TEST manifest records: `9848`; labels: `9848` objects; modality counts visible `4835`, infrared `5013`.
- Candidate contract: NCNN FP32, 480, confidence `0.25`, NMS IoU `0.70`, exactly one external NMS.
- PyTorch was not used for the primary result; no threshold sweep or candidate switching occurred.

The open event was written before any TEST image decode. Machine-readable audit: [`input_audit.json`](../../../.runtime/scope26/input_audit.json).
