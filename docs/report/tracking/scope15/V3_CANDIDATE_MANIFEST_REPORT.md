# V3 Candidate Manifest Report

Manifest ứng viên được tạo tại `/run/media/pnt/APP/anti_drone/data/processed/drone-single-class-v3-candidate/manifest.json` với **30,227 assigned samples**, mỗi sample đúng một lần.

| Candidate split | Samples |
|---|---:|
| train | 12,142 |
| val | 8,237 |
| test | 9,848 |
| Total | 30,227 |

Manifest có sample ID, V1/V2 reference, source image/label và hash, archive/member, annotation member, source sequence directory, frame index, modality, candidate prefix, original partition, candidate split, output paths và provenance status. Provenance được ghi là `CONFIRMED_SOURCE_SEQUENCE_ARCHIVE_MEMBER; SESSION_DISJOINT_UNVERIFIED`; không tạo source/session ID mới.

Scope 13 mapping cho 318 source sequences và 63 candidate prefixes được join theo source image path. Original partition được bảo toàn, visible/infrared cùng source sequence cùng split, và toàn bộ prefix cùng split. 6,505 quarantine samples không xuất hiện trong candidate manifest.

Hash manifest: `b5bc4cdf34b7e8283f4c1a6dd342f816f3ff1ad10f5fd3876baa413e35a55ffc`.
