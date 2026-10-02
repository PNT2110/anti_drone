# SPEC_DRONE_TRACKER adoption record

Date: 2026-09-28 (Asia/Ho_Chi_Minh)

Source reviewed: `/home/pnt/Downloads/SPEC_DRONE_TRACKER.pdf`

Source SHA-256: `2e90b60bd13b12c2a62ebe69392b7d472755430f97a37b56005290987f12d45a`

## Adopted

- P-only image-error control. Integral and derivative gains remain disabled.
- Three-sample median rejection for one-frame bounding-box jumps.
- Adaptive error filtering: responsive for large errors, stronger filtering near center.
- Per-axis hysteretic deadband, with a wider deadband on TILT.
- Braking taper near image center.
- Time-based velocity and acceleration limiting in addition to the absolute per-update cap.
- Immediate motion-velocity reset when the target is not observed; prediction-only tracks never command hardware.
- Stable HIGH-confidence acquisition gate before physical output. LOW-confidence observations may continue ByteTrack association but cannot independently arm physical motion.
- A non-blocking process lock so only one camera/GPIO tracking runner can be active.
- Camera capture buffer remains one frame (`CAP_PROP_BUFFERSIZE=1`) to minimize stale-frame backlog.
- The live USB launcher fixes exposure at `30 ms` (`exposure_time_absolute=300`) with gain `7`. The camera's aperture-priority mode produced severe full-frame motion blur during servo movement; the manual setting remains below the 40 ms frame period at 25 FPS while keeping the room usable.
- A fixed-pose A/B diagnostic proved that releasing PWM lets the load-bearing TILT axis sag and changes the camera view substantially. The installed runner now arms the calibrated PAN=90/TILT=120 pose at startup and holds the last valid pulse during detector loss. It sends no new position from blocked/predicted frames, and still disarms immediately on camera failure or process shutdown.

## Deliberately not copied

- The document's faster generic speed limits were not copied. The installed MG90S mount keeps the camera-tested conservative limits: PAN `0.80 deg/s`, TILT `0.60 deg/s`, with acceleration limits `1.50` and `1.00 deg/s^2` respectively.
- Appearance-memory/ReID was not added. The system exposes one session-level drone ID for UI continuity, but makes no unsupported cross-session identity claim.
- Kernel hardware PWM was not substituted for the currently verified LGPIO timed-wave path. The current transport phase-separates PAN and TILT pulses by 10 ms and has survived USB-camera operation without the prior all-zero-frame fault. A backend change requires a separate electrical/timing validation.
- A second capture thread was not introduced. The existing V4L2 MJPEG path requests a one-frame buffer, and the measured live pipeline has no evidence that a new thread would improve control enough to justify the concurrency risk.

## Installed control profile

Profile: `MEDIAN3_ADAPTIVE_P_ACCEL_LIMITED`

- `kp_pan = kp_tilt = 1.25`
- `deadzone = 0.04`
- `tilt_deadzone_scale = 2.0`
- `deadzone_hysteresis = 1.5`
- `brake_zone = 0.25`
- `max_step = 0.25 deg/update`
- `max_speed_pan = 0.80 deg/s`
- `max_speed_tilt = 0.60 deg/s`
- `max_accel_pan = 1.50 deg/s^2`
- `max_accel_tilt = 1.00 deg/s^2`
- median window = 3 observations
- near-center filter weight = `0.85`
- far-error filter weight = `0.50`

## Pi evidence

A physical hardware run used the USB camera and both MG90S channels with PAN on BCM GPIO12 and TILT on BCM GPIO13. During the observed run:

- camera remained enumerated;
- `get_throttled=0x0`;
- temperature was approximately `56.5 C`;
- effective display rate was approximately `13.3 FPS`;
- controller velocity returned to `0.0 deg/s` immediately after target loss;
- the last physical command was held rather than integrating error or chasing prediction-only tracks;
- clean shutdown returned GPIO12 and GPIO13 to input mode.

A subsequent A/B camera check showed that manual `8 ms`, gain `4` was too dark. Manual `20 ms`, gain `7` removed the auto-exposure blur but remained dark after the mount moved toward a low-light area, so the installed launcher uses `30 ms`, gain `7`; this is still shorter than the 40 ms frame period.

The latest frame after the target left view showed the ceiling and correctly produced `NO_TARGET`; no physical command was generated from that frame.

The fixed-pose diagnostic initially measured `0.30 px` median and `0.72 px` p95 over a mixed scene containing a moving person. A follow-up measurement on a static upper-right background region measured about `0.066 px` median and `0.106 px` maximum among reliable correlations while PWM held a constant pose. This confirms that release/re-arm movement—not fixed-pulse jitter or controller gain—is the dominant source of the visible jump.

## Verification

- Targeted servo/camera tests: `20 passed`.
- Full repository regression: `191 passed, 1 skipped`.
- `python -m compileall -q scripts src tests`: PASS.
- `git diff --check`: PASS.
- Pi single-instance smoke: second runner rejected with `TRACKING_INSTANCE_ALREADY_ACTIVE`; primary runner exited cleanly; both GPIOs remained input; no throttling.

## Operator note

For a meaningful smoothness check, keep the full drone visible, stationary at moderate distance for acquisition, and then move it slowly. A drone that is extremely close, hand-occluded, or outside the camera view causes intermittent detector observations; the controller correctly stops instead of guessing.
