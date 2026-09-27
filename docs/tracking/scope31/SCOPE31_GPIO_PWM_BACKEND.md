# Scope 31 — GPIO/PWM Backend Audit

Read-only Pi discovery and the Scope31R no-motion preflight found:

- `/usr/bin/pinctrl` available;
- `/usr/bin/gpioinfo` available;
- `/sys/class/pwm/pwmchip0` present;
- no active `pigpio`, `pigpiod`, servo, PWM, or GPIO process/service observed;
- `pinctrl get 12` and `pinctrl get 13` reported GPIO12/GPIO13 as `none`;
- `gpioinfo` reported GPIO12 and GPIO13 as inputs.

Selected backend for bounded commissioning: Linux kernel sysfs PWM through
`/sys/class/pwm/pwmchip0`, driver `rpi-pwm`, `npwm=4`. The Pi runtime used
`pwm1` for BCM GPIO13/PWM0_CHAN1 (PAN) and `pwm0` for BCM GPIO12/PWM0_CHAN0
(TILT), with `pinctrl` alternate function `a0`. The signal period was
20,000,000 ns (50 Hz); duty was expressed in nanoseconds. Configuration,
enable, disable, pinmux restoration to `none`, and unexport all succeeded.

The no-enable preflight passed. A single PAN 1500 us / 0.75 s command then
ran with the same backend and cleanup passed. Software evidence is therefore
consistent with a generated PWM command, but physical servo response was
`NO_RESPONSE`; this does not prove the signal reached the servo or that the
servo supply was present.

No competing GPIO stack or autostart was introduced. No TILT PWM was enabled.
