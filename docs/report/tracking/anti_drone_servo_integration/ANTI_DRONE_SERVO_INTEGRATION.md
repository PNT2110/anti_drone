# Anti-drone pan/tilt integration

This is the port of the working Pi5 pan/tilt control algorithm from
`dji-vision-tracking-feat-initial-pan-tilt-tracking` into this repository.
Only the control/transport layer was ported. The DJI detector, COCO/person
class handling, ESP32 transport, and target type were not copied.

## Data path

```text
frozen NCNN drone detector
  -> Scope 28 HIGH/LOW observations
  -> bytetrack_motion_adaptive
  -> anti_drone Track (source-frame xyxy)
  -> select_drone_target()
  -> DronePanTiltController
  -> NullServoTransport (default) or explicit PiDirectServoTransport
```

The detector contract remains unchanged: NCNN FP32, 480 input, confidence
`0.25`, tracker floor `0.10`, and one NMS at IoU `0.70`. The tracker remains
`bytetrack_motion_adaptive`.

## Ported control behavior

- proportional image-center error with the gains and smoothing profile from
  the working Pi5 controller;
- bounded software angles: PAN 20–160°, center 90°; TILT 30–140°, center
  120°;
- user-confirmed channel mapping: PAN BCM GPIO12, TILT BCM GPIO13;
- 50 Hz direct `lgpio` line-write transport, with cleanup returning both
  lines to input/low;
- predicted-only tracks are logged as `PREDICTED_BLOCKED` and are not sent to
  the transport; associated LOW observations are valid observed tracks;
- no autostart and no hardware access on import.

These angle/pulse values are the software envelope copied from the working
Pi project, not a new servo calibration claim. Physical commissioning and
safe mechanical limits remain governed by the existing Scope 31 evidence.

## Run modes

The command-run entry point is:

```bash
python scripts/anti_drone_pi_servo_tracking.py \
  --config configs/anti_drone_pi_servo.json
```

This is dry-run by default and records target/command state without GPIO,
PWM, serial, or servo writes. An explicit `--hardware` is required to create
the Pi direct transport. It is not a service and does not use V3 TEST.

The implementation files are:

- `src/anti_drone/servo/controller.py`
- `src/anti_drone/servo/direct.py`
- `src/anti_drone/servo/bridge.py`
- `scripts/anti_drone_pi_servo_tracking.py`

The port is covered by `tests/test_servo_integration.py`.
