# Scope 27 — Dry-run safety

Physical actuation was disabled by construction. `DryRunActuator` only computes and logs target-center errors; it does not import GPIO/PWM/serial actuator libraries and does not write to any hardware sink.

Evidence:

- `mode = DRY_RUN_ONLY`;
- `actuator_output_enabled = false` on every frame;
- GPIO writes `0`;
- PWM writes `0`;
- serial writes `0`;
- no autostart/systemd service created;
- no USB webcam or live camera opened.

The output is a command preview, not a servo simulation or physical actuator result.
