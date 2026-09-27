# Scope 31 — Power Audit

Status: `POWER_VOLTAGE_UNMEASURED_USER_ACCEPTED`.

Scope31R records that the user explicitly waived pre-motion voltage measurement and authorized bounded commissioning. The external supply and common ground remain user-confirmed facts only; the actual servo rail voltage, under-load voltage, ripple, and current margin remain **unmeasured**. This is not an electrical power-validation PASS.

The user also confirmed that servo V+ is not intentionally sourced from the Pi 5V rail. The Pi did not switch, enable, modify, or electrically probe the supply.

Because PAN produced `NO_RESPONSE` at the first bounded 1500 us command, physical commissioning is blocked pending inspection of the external supply, signal/ground wiring, servo connector orientation, and the servo itself. No further axis was pulsed.
