# Scope 25R — Pi reproduction

## Timeline

- Initial Scope 25 attempt: `FREEZE_REPRODUCTION_BLOCKED`; `192.168.1.118` was unreachable.
- Scope 25R resume: `PI_REPRODUCTION_PASS`.

## Access and identity

The host route was `192.168.1.47/24` on `enp3s0`; the Pi was reachable at `192.168.1.118` on the same LAN. SSH/TCP 22 and ICMP succeeded. No Tailscale or alternate path was used.

Remote identity matched the gate:

- `Raspberry Pi 5 Model B Rev 1.0`
- `aarch64`
- Linux kernel `6.18.50+rpt-rpi-2712`
- 4 GiB-class RAM
- temperature `40.0'C → 49.4'C`
- throttling `0x0 → 0x0`

The existing Scope 21 NCNN environment was reused. Runtime was NCNN `1.0.20260526`, 4 threads. Scope 25 used the separate remote workspace `/home/pitan/antidrone-scope25-smoke`.

## Transfer, parity, and latency

Only the verified NCNN pair, fixed 8-image TRAIN smoke subset, manifest/reference, and runner were transferred. No TEST image or full dataset was transferred.

- warmup: 20 per image;
- measured: 20 per image, 160 inferences total;
- fixed inputs: 8/8 TRAIN images;
- parity: 8/8 `PARITY_PASS`;
- maximum confidence absolute difference: `0.0012343526`;
- minimum bbox IoU: `0.9717433387`;
- mean measured end-to-end latency: `43.2502 ms`;
- mean derived FPS: `23.1218`;
- artifact hashes: exact match on Pi;
- `test_accessed`: `false`.

Machine-readable evidence: [`pi_smoke_result.json`](../../../.runtime/scope25/pi_smoke_result.json).
