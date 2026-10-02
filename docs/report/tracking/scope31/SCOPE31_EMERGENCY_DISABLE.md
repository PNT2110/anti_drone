# Scope 31 — Emergency Disable

The Scope31R commissioning tool implements bounded duration, explicit
single-axis selection, append-only JSONL logging, and cleanup in `finally`.
The no-enable preflight passed. The PAN center command exited normally and
disabled/unexported `pwm1`, restored GPIO13 to `none`, and logged zero cleanup
errors. No TILT channel was touched.

Ctrl+C and injected-exception paths are implemented in the tool but were not
physically exercised after the PAN `NO_RESPONSE` stop. No command loop or
autostart remains active. Further physical tests are blocked pending wiring/
power inspection.

Physical output in the resumed attempt: one bounded PAN PWM command; serial,
motor, and detector/tracker-to-servo writes = `0`.
