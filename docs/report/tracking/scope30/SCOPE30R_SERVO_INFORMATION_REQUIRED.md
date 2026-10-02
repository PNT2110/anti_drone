# Scope 30R — Servo Information Required

Physical commissioning remains blocked by `SERVO_BOUNDS_UNKNOWN`. Scope 30R2 now records the user-provided channel mapping only:

- PAN control: BCM GPIO13
- TILT control: BCM GPIO12

This mapping does not identify the installed servo, establish a PWM implementation, or authorize GPIO/PWM initialization. The repository still contains no authoritative evidence for the installed pan actuator model, tilt actuator model, controller/driver, servo power supply arrangement, neutral/min/max command limits, command frequency, or command units.

Provide exact evidence before any future hardware scope:

- photo or model number for the pan actuator;
- photo or model number for the tilt actuator;
- controller board model and control method (PWM/PCA9685/MCU/serial/etc.);
- pan and tilt channel mapping beyond the recorded BCM GPIO13 / BCM GPIO12 mapping, if a controller-specific mapping is different;
- external servo supply voltage/current arrangement;
- documented safe neutral, minimum, and maximum commands with units.

No generic servo values are accepted and no hardware was initialized.
