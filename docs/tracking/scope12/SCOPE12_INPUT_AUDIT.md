# Scope 12 — Input Audit

Audit date: 2026-09-22. Baseline was read before materialization.

| Input | SHA-256 | Result |
|---|---|---|
| V1 `manifest.json` | `3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d` | 36,732 rows |
| V1 `split_registry.json` | `7bc14c2e05b690f2df6c0cfb92e03b565a200f16dd0ef110df8e464837a63a54` | unchanged |
| V1 `audit.json` | `f25e3b3e199befecc325e6750cba1f81299e103042a3170618ae09f1ec6e06b2` | unchanged |
| V1 `data.yaml` | `45c1f50e917b6a2c1b235d019ad33fceb1bbe9c82b4b770705656647e79fe49f` | unchanged |
| V2 `manifest.json` | `9605532a2b24566b691554125074c37f198c452bce343883b2a6720847299aa1` | unchanged |
| V2 `split_registry.json` | `5819f6df78156561f3907e0eac05186dd5d77fe556699c74bad0ee5d40f51ed9` | unchanged |
| V2 `audit.json` | `ab6a02db3b5efdff5f4c95d130ab4f9b06eddd18b9541aa7157ebb86f016a120` | `PASS` |

The locked V2 totals are 36,732 source rows, 30,227 `ASSIGNED` rows, 6,505 `QUARANTINED` rows, 318 verified groups, seed 42, and zero verified-group overlap in the accepted V2 audit. No V1/V2 manifest, registry, audit, checkpoint, tracker, gate, or historical report was edited.

The working tree already contained unrelated prior-scope modifications and untracked artifacts; they were preserved.

## Capacity check

The source image+label estimate was 2,388,255,708 bytes. Free space before copy was 16,891,723,776 bytes; the 10% safety estimate plus 256 MiB was 2,895,516,734 bytes. The copy completed atomically and the resulting dataset occupies about 2.26 GiB.

Machine-readable baseline and materialization evidence is under `.runtime/scope12/` and `data/processed/drone-single-class-v2-executable/`.
