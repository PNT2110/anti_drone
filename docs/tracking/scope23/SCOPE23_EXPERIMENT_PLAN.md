# Scope 23 — Frozen experiment plan

The plan was written before E1 results existed. Maximum configurations per primary candidate: 4, including the Scope 22 reference E0. The approved sequence was E1 → E2 → E3, stopping if both v8 primary candidates passed. YOLOv11n-480 was secondary-only after a v8 pass. No configuration outside this plan was run.

Machine-readable source: [`experiment_plan.json`](../../../.runtime/scope23/experiment_plan.json).

Acceptance required zero detection-count mismatch, zero class mismatch, minimum bbox IoU >= 0.90, maximum confidence absolute shift <= 0.20, and no systematic loss on the 32-image secondary TRAIN diagnostic set.
