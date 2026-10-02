# Scope 31 — Input Audit

Final status: `PAN_NEUTRAL_COMMISSIONING_BLOCKED`.

| Item | Result |
|---|---|
| Raspberry Pi | Raspberry Pi 5 Model B Rev 1.0, aarch64 |
| PAN servo | User-confirmed MG90S |
| TILT servo | User-confirmed MG90S |
| PAN signal | User-confirmed BCM GPIO13 |
| TILT signal | User-confirmed BCM GPIO12 |
| Supply topology | User-confirmed dedicated/external supply and common ground |
| Actual supply voltage | **Not measured or otherwise evidenced; user waiver recorded** |
| Frozen detector hashes | PASS |
| Scope 26 headline | PASS |
| V3 TEST | Not accessed |
| Physical PWM/GPIO output | One bounded PAN command; cleanup PASS; TILT untouched |

The user explicitly waived the pre-motion voltage measurement. The selected
software PWM path was checked and a single PAN 1500 us / 0.75 s command was
issued; the user observed `NO_RESPONSE`, so commissioning stopped.
