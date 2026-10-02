# Scope 13 — Session Prefix Audit

There are 63 total RGBT date/time prefixes. Of these, 59 contain more than one V2 group and are the candidate prefixes carried from Scope 12; 47 of those 59 appear in multiple V2 splits.

## Status counts

| Scope 13 status | All 59 candidate prefixes | 47 cross-split prefixes |
|---|---:|---:|
| `CONFIRMED_SHARED_SESSION` | 0 | 0 |
| `CONFIRMED_DISTINCT_SOURCES` | 59 | 47 |
| `UNRESOLVED` | 0 | 0 |

`CONFIRMED_DISTINCT_SOURCES` means that each full `<date>_<time>_<stream>_<sequence>` maps to a distinct archive sequence directory with its own visible/infrared member pair and annotation JSON. It does **not** mean that the archive proves independent human recording sessions.

At the session level, the result is different: the archive exposes no explicit `session_id` or metadata rule joining/splitting directories that share the date/time prefix. Therefore all 59 prefixes have session relationship `UNRESOLVED`; the 47 cross-split prefixes remain UNKNOWN for session collision.

The audit never promoted equal timestamps to a shared session. Full prefix evidence is in `.runtime/scope13/session_prefix_audit.csv`; every row lists archive sequence IDs, groups, V2 splits, and the decision reason.
