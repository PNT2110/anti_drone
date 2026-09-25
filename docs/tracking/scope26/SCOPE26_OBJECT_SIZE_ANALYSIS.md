# Scope 26 — Object-size analysis

Frozen policy: project-specific bins by `max(bbox_width, bbox_height)` in source pixels: `<4`, `4-8`, `8-16`, `16-32`, `32-64`, `>64`. No size bin was filtered or used for tuning.

| Size bin | GT objects | TP | FN | Recall |
|---|---:|---:|---:|---:|
| <4 | 0 | 0 | 0 | 0.00000 |
| 4-8 | 0 | 0 | 0 | 0.00000 |
| 8-16 | 1 | 0 | 1 | 0.00000 |
| 16-32 | 795 | 656 | 139 | 0.82516 |
| 32-64 | 4321 | 3619 | 702 | 0.83754 |
| >64 | 4731 | 4327 | 404 | 0.91461 |

AP is `N/A` for this analysis because the evaluator does not implement COCO ignore-area semantics. Reference headline hash: `7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83`.
