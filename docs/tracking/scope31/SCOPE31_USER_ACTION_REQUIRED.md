# Scope 31 — User Action Required

Before any future physical servo command, provide:

- measured voltage between external servo V+ and servo GND while connected;
- external power-supply model or trusted setpoint;
- whether the voltage was measured under load;
- confirmation that servo V+ is not connected to the Pi 5V rail;
- confirmation that the shared ground is physically present.

Do not provide only a nominal MG90S voltage range. The actual installed supply voltage is the blocking evidence.
