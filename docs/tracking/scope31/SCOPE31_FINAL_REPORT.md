# Scope 31 — Final Report

Final status: `PAN_NEUTRAL_COMMISSIONING_BLOCKED`.

Scope31R was resumed under the explicit user waiver. The supply voltage is
still unmeasured and remains `POWER_VOLTAGE_UNMEASURED_USER_ACCEPTED`; it is
not reported as verified. Backend preflight passed, one bounded PAN center
command was issued, cleanup passed, and the user observed `NO_RESPONSE`.
Commissioning stopped immediately: no direction/limit discovery and no TILT
command were attempted.

Resume command and evidence:

```text
sudo .../scope31_commission.py --axis pan --pulse-us 1500 --duration 0.75 \
  --accept-unmeasured-supply
```

The Pi log records the bounded enable at `2026-09-26T16:48:50.858892+00:00`
UTC and cleanup at `2026-09-26T16:48:51.613015+00:00` UTC. The user supplied
the physical observation `NO_RESPONSE` after the center command. A follow-up
bounded micro-step sequence (`1500 → 1450 → 1500 → 1550 → 1500 us`) was run;
its physical result is pending observation. The read-only mux
check independently showed GPIO13=`a0 / PWM0_CHAN1`, period `20,000,000 ns`,
duty `1,500,000 ns`, enable `0` after cleanup, and GPIO12/13 returned to
`none`.

| Question | Result |
|---|---|
| External servo voltage | Unmeasured; user waiver recorded; not electrically validated |
| Separate supply/common ground | User-confirmed; not electrically revalidated by Pi |
| PWM backend | Linux sysfs PWM, `rpi-pwm`, 50 Hz; software setup/cleanup PASS |
| PAN/TILT GPIO | BCM13 / BCM12, user-confirmed |
| PAN neutral | 1500 us command issued; physical response `NO_RESPONSE`; not calibrated |
| TILT neutral | Not tested |
| Safe min/max/direction/rate | Not established |
| Emergency/cleanup | Normal-exit cleanup PASS; Ctrl+C/exception implemented but not physically exercised |
| Camera coexistence | Not run after the blocked commissioning |
| Physical writes | One bounded PAN PWM command; serial/motor/AI-to-servo = 0 |
| Detector/tracker connection | None |
| Scope 26/V3 TEST | Frozen / not accessed |
| Regression | 161 passed, 1 skipped; compileall PASS; git diff --check PASS |
| Final status | `PAN_NEUTRAL_COMMISSIONING_BLOCKED` |

Required next action before any retry: inspect servo V+/GND/signal wiring,
connector orientation, external supply presence, and common ground; if the
user continues despite the waiver, keep the voltage unmeasured in all reports.
No Scope 32 was started and automatic tracking remains disabled.
