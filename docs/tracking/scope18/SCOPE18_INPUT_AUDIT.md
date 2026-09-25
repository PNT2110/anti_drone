# Scope 18 — Input audit

Generated: `2026-09-24T08:56:34.944087+00:00`. Scope: controlled detector training only; no Git commit/push.

## Locked inputs

- Dataset: `/run/media/pnt/APP/anti_drone/data/processed/drone-single-class-v3-labelrepair-candidate`
- Repaired manifest SHA-256: `bf814c1899d0ed006ac6f27bec465bdb1e32e5bdd3962983e740345991076c45`
- Repaired split registry SHA-256: `c922808e726e378c5a7c10273523b8a4e2cd3a134aff6b45973f70ab1703f3b1`
- Repaired `data.yaml` SHA-256: `302dc33a70f81ceea9f3067855a347a17c98a2ef8e1fb5e7b4c20cc83d062e53`
- Scope 17 repair audit SHA-256: `bb17d508aaae28e523734a33852e53fb3c8f2cb31078ab03c24d47bf81ddd914`
- Source mapping: `/run/media/pnt/APP/anti_drone/.runtime/scope13/rgbt_archive_mapping.csv` (SHA-256 `ffb0d14247ff02f9d30e14011769435fd296103e4fe735e02abbb30cd1396d4e`)
- Original V3 candidate manifest: `b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc`
- Original V3 candidate registry: `57ffb56effd35ad65aad9d163e586ebd8c9f9f1f19c93a86d5fd7619d72cff3d`

## Scope boundaries

Only `drone-single-class-v3-labelrepair-candidate` is used. The quarantined 6,505 samples / 4,172 groups are excluded. V1, V2, the original V3 candidate, Scope 15/16 artifacts, tracker/gate code and the V1 checkpoint are not modified. Test is locked and is not used for training or selection. Halmstad remains diagnostic-only and `SPLIT_UNVERIFIED`.

Input audit status: **PASS**. Config preparation status: **PASS**.
