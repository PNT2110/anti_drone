# Scope 12 — Assigned Source Provenance

## Result

All 30,227 assigned samples have a readable V1 source path and an image SHA-256 matching the V2 manifest. The 318 groups are consistently derived from the repository's actual `prepare_dataset.py` rule: for `RGBT_..._<modality>_<frame>.jpg`, remove the modality and frame suffix, retaining the `RGBT` split/date/time/stream/sequence fields.

| Evidence | Count |
|---|---:|
| Assigned samples | 30,227 |
| Verified RGBT groups | 318 |
| Local source path exists and image hash matches | 30,227 |
| Visible samples | 14,713 |
| Infrared samples | 15,514 |
| Archive/member-confirmed samples | 0 |
| Groups with archive/member proof | 0 |

The V1/V2 manifest preserves local source paths and the RGBT filename fields, but it does not preserve an archive name/member key for `base` rows. The source archive inventory therefore cannot be used to claim archive-level sequence identity or source-disjointness for the assigned data. This is intentionally recorded as `UNVERIFIED_ARCHIVE_MEMBER`; it is not upgraded from filename similarity.

## Session-candidate warning

The date/time prefix is a useful candidate session key, not a confirmed source-session key. There are 59 candidate prefixes shared by multiple group IDs; 47 have groups assigned across more than one V2 split. This is a provenance warning, not a proven `SOURCE_GROUP_ALIAS`, because no archive/session metadata is available to establish that these group IDs are the same physical source sequence. The executable dataset keeps the accepted 318-group assignment unchanged.

If future archive metadata proves any of these candidates to be one source sequence, the current V2 must be treated as source-disjointness-unverified and rebuilt under an approved rule before making a generalization claim. No such rebuild was performed here.

Machine-readable evidence:

- `.runtime/scope12/source_provenance.json`
- `.runtime/scope12/source_provenance_rows.jsonl`
- `scripts/audit_scope12_source_provenance.py`
