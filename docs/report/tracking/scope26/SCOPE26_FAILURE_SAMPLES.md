# Scope 26 — Deterministic failure samples

The machine-readable failure set is [`failure_samples.json`](../../../.runtime/scope26/failure_samples.json), bound to headline hash `7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83`.

Selection rules are deterministic: highest-confidence FP, lowest-IoU TP, lowest-best-IoU FN, then modality and small-object subsets with stable sample-ID tie breaks; at most 10 per category.

These samples are for post-hoc diagnosis only. They were not used to change the model, threshold, backend, or headline result.
