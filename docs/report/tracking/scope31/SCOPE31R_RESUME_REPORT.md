# Scope 31R — Resume Report

## Result

`PAN_NEUTRAL_COMMISSIONING_BLOCKED`

The user waived pre-motion voltage measurement. The evidence status remains
`POWER_VOLTAGE_UNMEASURED_USER_ACCEPTED`; no voltage value was invented.

## Sequence

1. Verified the existing frozen hashes and Pi5 identity from Scope31 evidence.
2. Rechecked GPIO12/13 ownership and found no competing servo/PWM process.
3. Selected Linux kernel sysfs PWM (`rpi-pwm`, `pwmchip0`), mapping PAN GPIO13
   to `PWM0_CHAN1`/`pwm1` and TILT GPIO12 to `PWM0_CHAN0`/`pwm0`.
4. Ran export/configure/disable/unexport preflight without enabling PWM.
5. Issued one explicit PAN command: 1500 us, 50 Hz, 0.75 s, TILT disabled.
6. Cleanup completed with zero errors; GPIO13 returned to `none` and no PWM
   channel remained exported.
7. The user previously reported `NO_RESPONSE` for the 1500 us center command.
   To distinguish “already centered” from a dead signal path, the prescribed
   bounded PAN micro-step sequence `1500 → 1450 → 1500 → 1550 → 1500 us` was
   run. Its physical result is pending user observation; no TILT pulse,
   optional 1400/1600 probe, endpoint discovery, camera coexistence, or
   two-axis test has been attempted.

## Safety boundaries

- detector, tracker, thresholds, NCNN artifacts, and Scope26 headline were not
  changed;
- no detector/tracker-to-servo path was connected;
- no V3 TEST access;
- no serial, motor, GPIO actuator, or autostart command;
- no further physical retry after `NO_RESPONSE`.

The next permitted action is hardware-side inspection of external supply
presence, V+/GND/signal wiring, connector orientation, and common ground.
Voltage remains unmeasured even if a future retry is authorized.
