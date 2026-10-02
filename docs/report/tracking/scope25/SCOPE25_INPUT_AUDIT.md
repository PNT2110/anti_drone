# Scope 25 — Input audit

Status: **INPUTS VERIFIED; FREEZE BLOCKED AT PI REPRODUCTION**.

- Primary review candidate: `scope18-yolov8n-480:ncnn`.
- `best.pt` SHA-256: `359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e` — exact match.
- NCNN `.param` SHA-256: `8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5` — exact match.
- NCNN `.bin` SHA-256: `23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7` — exact match.
- Scope 20 NCNN parity: `PARITY_PASS`.
- Scope 21 Pi evidence: `PI_BENCHMARK_PASS`, 22.493 FPS, NCNN 1.0.20260526, 4 threads.
- Dataset manifest SHA-256: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`.
- Split registry SHA-256: `c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1`.
- Fixed smoke input set: 8 TRAIN images; `test_accessed=false`.

Machine-readable audit: [`input_audit.json`](../../../.runtime/scope25/input_audit.json).
