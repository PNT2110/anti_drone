# Scope 30 — Servo Discovery

User-provided channel mapping has been recorded for Scope 30R2:

- PAN control: BCM GPIO13
- TILT control: BCM GPIO12

This is channel mapping only. No authoritative servo model, GPIO/PWM controller implementation, serial controller, power arrangement, or calibrated command-unit specification has been established. The repository’s dry-run layers expose preview fields only and do not initialize hardware.

Status: `SERVO_BOUNDS_UNKNOWN`.

Physical commissioning remains `PHYSICAL_SERVO_COMMISSIONING_BLOCKED_BY_UNKNOWN_BOUNDS`. The mapping does not establish neutral/min/max, pulse width, PWM frequency, angle, or supply requirements. No GPIO mode, PWM, serial, servo, motor, or power rail was touched.

## Scope 30R2 / Attempt 4

Channel mapping remains PAN = BCM GPIO13 and TILT = BCM GPIO12, mapping only. No PWM/GPIO initialization occurred. Servo model, supply arrangement, neutral/min/max, pulse width, frequency, angle, and command units remain unknown; commissioning stays blocked.
