# Scope 26 — Error analysis

Error matching used IoU `0.50` and the frozen confidence output. Counts are event counts: localization errors can contribute one unmatched-prediction event and/or one unmatched-GT event.

| Category | Count |
|---|---:|
| FALSE_NEGATIVE | 1096 |
| FALSE_POSITIVE | 399 |
| LOCALIZATION_ERROR | 306 |

`CONFIDENCE_BELOW_FROZEN_THRESHOLD`: **not observable** because the production runner retained only post-threshold detections. `NMS_INTERACTION`: **not observable** because pre-NMS candidates were not retained. These are not reported as zero.

One-class confusion representation: drone TP `8602`, background FP `555`, background FN `1246`.

Machine-readable analysis: [`error_analysis.json`](../../../.runtime/scope26/error_analysis.json).
