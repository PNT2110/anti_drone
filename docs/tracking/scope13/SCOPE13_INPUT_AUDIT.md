# Scope 13 — Input Audit

Audit date: 2026-09-22. No accepted artifact was modified.

| Artifact | SHA-256 |
|---|---|
| V1 manifest | `3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d` |
| V1 split registry | `7bc14c2e05b690f2df6c0cfb92e03b565a200f16dd0ef110df8e464837a63a54` |
| V2 manifest | `9605532a2b24566b691554125074c37f198c452bce343883b2a6720847299aa1` |
| V2 split registry | `5819f6df78156561f3907e0eac05186dd5d77fe556699c74bad0ee5d40f51ed9` |
| V2 audit | `ab6a02db3b5efdff5f4c95d130ab4f9b06eddd18b9541aa7157ebb86f016a120` |
| Executable V2 manifest | `c66e201aae060b96687c841d54a3297a1ea9fe7788d9101521bffe87f43db9aa` |
| Executable V2 data.yaml | `38dabc580af21f5ed36f1d578f6b00c99f7efc9300ae72d105c6d44909cf8216` |
| Scope 12 source provenance | `3ad585d1a696cee996684a7928ba62901181ac0bb3566c50c8ed9d838a3b3f95` |

Expected counts matched: 318 RGBT groups, 30,227 assigned samples, 6,505 quarantined samples, 59 multi-group candidate prefixes, 47 cross-split candidate prefixes, and 0 archive/member-confirmed samples in Scope 12 before this audit.

The six-archive inventory was read from the accepted Scope 10 evidence. `Anti-UAV300.tar` is the only candidate with a direct structural match to the RGBT names: 318 sequence directories, each with visible/infrared MP4 and JSON members. Its accepted inventory SHA-256 is `c8af3934b7b84c21f1ecfda4723c11b186a6c7182c1ece2b629ebc2035fa6e2f`; the 16.8 GB archive was not rehashed in this scope.

Machine-readable baseline: `.runtime/scope13/rgbt_provenance_summary.json`.
