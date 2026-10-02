# Scope 24 — Backend comparison

| Model | Backend/path | Quantized artifact | Host parity | Pi parity | Pi benchmark | Decision |
|---|---|---|---|---|---|---|
| v8n-480 | TFLite T1 | full INT8, invoke blocked | BLOCKED | N/A | N/A | diagnostic-only |
| v8n-480 | TFLite T2 | full INT8, loads | FAIL | N/A | N/A | diagnostic-only |
| v8n-640 | TFLite T1 | full INT8, invoke blocked | BLOCKED | N/A | N/A | diagnostic-only |
| v8n-640 | TFLite T2 | missing after timeout | BLOCKED | N/A | N/A | blocked |
| v8n-480/640 | ORT O1 QDQ | graph generated, runtime invalid | BLOCKED | N/A | N/A | blocked |

No candidate satisfies `INT8_READY_FOR_FREEZE_REVIEW`. No TEST accuracy was used and Scope 21 FP32 Pi measurements were not relabeled.
