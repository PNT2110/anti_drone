# Scope 26 — Headline results

Status: **`FINAL_TEST_COMPLETE`**.

| Metric | Result |
|---|---:|
| TEST expected / processed / skipped | 9848 / 9848 / 0 |
| Precision @ frozen threshold | 0.93939 |
| Recall @ frozen threshold | 0.87348 |
| F1 @ frozen threshold | 0.90524 |
| mAP50 | 0.86724 |
| AP75 | 0.47675 |
| mAP50-95 | 0.47765 |
| TP / FP / FN | 8602 / 555 / 1246 |

Frozen contract: NCNN FP32, 480×480, confidence `0.25`, NMS IoU `0.70`. Metric definition: 101-point interpolated AP over frozen NCNN predictions retained at confidence ≥ 0.25; greedy per-image one-to-one matching; IoU 0.50:0.95 step 0.05.

Headline result SHA-256: `7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83`. Machine-readable result: [`headline_result.json`](../../../.runtime/scope26/headline_result.json).
