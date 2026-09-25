# Scope 14 — Input Audit

Audit date: 2026-09-22. All baseline checks passed before the dry run.

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
| Scope 13 archive mapping | `ffb0d14247ff02f9d30e14011769435fd296103e4fe735e02abbb30cd1396d4e` |
| Scope 13 prefix audit | `84c3d1c9f09c472b1936fda629a9e46da97c7029a0984efebe580e593656537c` |
| Scope 13 summary | `baa3f6153e8d4c7aaeb9f9e6cfa7d94e4253715979598d955e957c92ddd7d657` |
| Frozen V1 YOLOv8n checkpoint | `662fbc1c066041345970f4211a6ceb9209907a331fd1724c0b2be7e53a4beec1` |

Baseline counts matched: 30,227 assigned samples, 318 mapped source sequence directories, 6,505 quarantined samples, 63 total prefixes, 59 multi-group candidate prefixes, 47 cross-split prefixes, 0 sequence collisions, and UNKNOWN session relationship for the 47 cross-split prefixes.

No V1/V2/executable artifact, checkpoint, tracker, gate, quarantine row, or historical report was modified. No production V3 directory or `data.yaml` was created.
