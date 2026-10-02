# Scope 24 — TFLite host parity

T2 v8n-480 host parity: **FAIL**.

- Fixed 8: count mismatch `8/8`, class mismatch `0`, min IoU `1.000000`, max confidence shift `0.000000`.
- Secondary 32: count mismatch `32/32`, class mismatch `0`, min IoU `1.000000`, max confidence shift `0.000000`.
- T1 v8n-480/v8n-640 were runtime-blocked; T2 v8n-640 had no completed full-integer artifact.

The fixed thresholds remained confidence `0.25`, NMS IoU `0.70`, min IoU `0.90`, and max confidence shift `0.20`.
