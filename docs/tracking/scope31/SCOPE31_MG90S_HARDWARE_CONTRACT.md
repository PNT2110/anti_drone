# Scope 31 — MG90S Hardware Contract

Known facts are limited to user-provided actuator identity and signal mapping:

- PAN: MG90S, BCM GPIO13
- TILT: MG90S, BCM GPIO12
- dedicated/external servo supply;
- Raspberry Pi and servo ground reportedly common.

The installed servo variant, supply voltage, controller implementation, pulse limits, PWM frequency, mechanical center, direction, and safe travel limits are not yet evidenced. No generic MG90S values are adopted.

Scope31R status: `POWER_VOLTAGE_UNMEASURED_USER_ACCEPTED`; the user waived
pre-motion voltage measurement. This is not a verified electrical power gate.
Physical commissioning is additionally blocked by PAN `NO_RESPONSE` at the
first bounded center command. No generic MG90S limits are adopted.
