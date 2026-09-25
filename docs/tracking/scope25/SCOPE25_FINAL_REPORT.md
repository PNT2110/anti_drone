# Scope 25R — Final report

## Final status

**`FP32_NCNN_CANDIDATE_FROZEN`**

## Acceptance answers

1. **Access route:** local LAN SSH to `192.168.1.118` from host `192.168.1.47/24` via `enp3s0`.
2. **Hardware:** `Raspberry Pi 5 Model B Rev 1.0`, `aarch64`, 4 GiB-class RAM.
3. **Candidate hashes:** exact match. `best.pt`: `359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e`; NCNN param: `8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5`; NCNN bin: `23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7`.
4. **Pi parity:** `8/8 PARITY_PASS`; max confidence difference `0.0012343526`; minimum bbox IoU `0.9717433387`.
5. **Latency sanity:** 20 warmup + 20 measured per image; mean end-to-end `43.2502 ms`, mean derived `23.1218 FPS`.
6. **Thermals:** `40.0'C → 49.4'C`; throttling `0x0 → 0x0`.
7. **Production package:** created at `artifacts/production-candidate/scope25/`.
8. **Package verification:** `SHA256SUMS` and independent package hash verification PASS.
9. **Freeze manifest:** SHA-256 `e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964`.
10. **TEST:** remains locked; `test_accessed=false`.
11. **Final state:** `FP32_NCNN_CANDIDATE_FROZEN`.

## History and boundaries

The initial Scope 25 attempt was `FREEZE_REPRODUCTION_BLOCKED` because the Pi was unreachable. Scope 25R restored the existing LAN route and passed the reproduction gate using the same candidate and fixed 8-image TRAIN subset. No retraining, export regeneration, INT8 work, dataset/label/split change, tracker/camera/servo work, or Git commit/push occurred. Non-selected research artifacts were retained. `SESSION_DISJOINT` remains `UNVERIFIED`.
