# Scope 28 — HIGH Stream Equivalence

Result: `PASS`

Fixed 8-image TRAIN parity: all 8 passed the Scope 20/21 gate (exact detection count and class, confidence absolute difference <= 0.05, bbox IoU >= 0.95). Across the Halmstad diagnostic sequence, the high stream passed **301/301** frame comparisons against the Scope 27 public reference; failures: 0.

| Metric | Value |
|---|---|
| 8-image max confidence absolute difference | 0.001234353 |
| 8-image minimum bbox IoU | 0.971743339 |
| Halmstad frames compared | 301 |
| Halmstad high-stream pass frames | 301 |
| Halmstad high-stream failures | 0 |
| NMS applications per dual frame | 1 |
| NCNN inferences per frame | 1 |

This is equivalence under the frozen acceptance gate; no model, threshold, backend, or postprocess tuning was performed.
