# Scope 24 — Final report

## Decision

**`PTQ_INT8_PATHS_EXHAUSTED_FOR_CURRENT_SCOPE`**.

Scope 23 NCNN INT8 was already blocked. Scope 24's bounded alternate paths also failed:

- TFLite T1 generated real full-integer artifacts but runtime invocation was blocked by the quantized `LOGISTIC` scale contract.
- TFLite T2 v8n-480 generated a loadable full-integer artifact but failed host parity on fixed-8 and secondary-32; T2 v8n-640 timed out before a complete artifact.
- ORT O1 static QDQ per-channel INT8 generated graphs rejected by ORT because of unsupported `DequantizeLinear axis` attributes.

No alternate artifact was eligible for Pi transfer. Pi 5 access was verified, but no INT8 runtime was installed, no artifact was copied, and no INT8 benchmark was run. Production model freeze was not performed.

The next authorized step is FP32 NCNN production-freeze review. Do not start QAT, 320 training, TEST evaluation, NCNN PTQ brute force, or a third INT8 backend within this scope.

V3 TEST remains locked; `SESSION_DISJOINT` remains UNVERIFIED; checkpoint and split baselines remain unchanged.

Machine-readable summary: [`final_summary.json`](../../../.runtime/scope24/final_summary.json).
