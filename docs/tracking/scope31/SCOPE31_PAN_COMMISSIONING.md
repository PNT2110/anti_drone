# Scope 31 — PAN Commissioning

Status: `PAN_NEUTRAL_COMMISSIONING_BLOCKED`.

Scope31R executed exactly one bounded manual command on BCM GPIO13: 50 Hz,
1500 us, 0.75 s, with TILT disabled. The software backend configured
`PWM0_CHAN1`, enabled the pulse, and cleanup completed with no errors. The
user observed `NO_RESPONSE`.

The prescribed small direction sequence was then run: `1500 → 1450 → 1500 →
1550 → 1500 us`, 0.35 s per step, 0.20 s pauses. Software cleanup passed and
no PWM remained active. Physical observation of that sequence is still
pending; no optional 1400/1600 probe, endpoint discovery, direction
calibration, or rate-limit calibration is accepted yet. Do not issue another
sequence until response and safety are physically confirmed.
