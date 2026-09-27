# Scope 28 — Dry-Run Safety

- `DRY_RUN_ONLY` was hard-coded in the adapter sink.
- GPIO writes: 0; PWM writes: 0; serial writes: 0.
- No webcam, servo, live targeting, autostart, or system service was used.
- `command_preview` contains only target center/error preview and no hardware command.
- Scope 26 TEST and all V3 TEST images were excluded from the run.
