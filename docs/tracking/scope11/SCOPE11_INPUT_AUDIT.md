# Scope 11 — Input Audit

Audit date: 2026-09-22. Repository: `/run/media/pnt/APP/anti_drone`.

## Baseline lock

The accepted V1/V2 artifacts were read before mapping. All observed hashes matched the previously accepted baseline, V2 audit status was `PASS`, and `independent_validation_claim` remained `false`.

| Artifact | SHA-256 | Count/status |
|---|---|---:|
| `data/processed/drone-single-class/manifest.json` | `3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d` | 36,732 V1 samples |
| `data/processed/drone-single-class-v2/manifest.json` | `9605532a2b24566b691554125074c37f198c452bce343883b2a6720847299aa1` | 36,732 V2 samples |
| `data/processed/drone-single-class-v2/split_registry.json` | `5819f6df78156561f3907e0eac05186dd5d77fe556699c74bad0ee5d40f51ed9` | 6,505 quarantined samples; 4,172 unverified groups |
| `data/processed/drone-single-class-v2/audit.json` | `ab6a02db3b5efdff5f4c95d130ab4f9b06eddd18b9541aa7157ebb86f016a120` | `PASS` |

The quarantine source totals are 4,171 `base` samples and 2,334 `my_dataset` samples. No manifest, label, image, split registry, checkpoint, or V2 assignment was edited.

## Archive checksums

The archives were read in place; no bulk extraction was performed.

- `data/import_data_rar/DUT-Anti-UAV.tar`: SHA-256 `5e7c17b051120d731fe7ac289db1328012daf41f4d8ff349cfe366dc7e926e34`.
- `data/import_data_rar/my_dataset.tar.xz`: SHA-256 `43a3f2a25a175b5e043b789309a89fbf33493f2815bec5ac4effb29296f47caf`.

## Audit method

`scripts/run_scope11_provenance_audit.py` maps every quarantined row to archive members and compares SHA-256 image content against the V1 `image_hash`. DUT tracking JPGs were hashed across the complete tracking archive, not only at the same filename, so basename similarity cannot silently become provenance confirmation. The flat `my_dataset` archive has image/label members but no video/session/frame metadata; it is therefore not classified as an independent image.

Machine-readable input evidence is in `.runtime/scope11/input_audit.json`.
