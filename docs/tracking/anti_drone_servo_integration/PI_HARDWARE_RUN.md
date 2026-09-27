# Pi hardware integration evidence

Run date: 2026-09-27 (Asia/Ho_Chi_Minh)

Target: Raspberry Pi 5 Model B Rev 1.0, `aarch64`, user `pitan`.

Input was the diagnostic Halmstad `V_DRONE_001.mp4` sequence, 301 frames.
The V3 TEST split was not accessed.

## Frozen detector/tracker contract

- backend: NCNN FP32;
- param SHA-256: `8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5`;
- bin SHA-256: `23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7`;
- public confidence: `0.25`;
- NMS IoU: `0.70`;
- tracker: `bytetrack_motion_adaptive`.

## Result

The anti_drone port processed all 301 frames with the explicit hardware
transport. It created track IDs 1–5, produced 220 observed target frames, 28
predicted-only frames that were blocked from servo commands, and 53 no-target
frames. Effective processing rate was approximately 21.27 FPS.

Mapping was PAN=BCM GPIO12 and TILT=BCM GPIO13, with software centers PAN=90°
and TILT=120°. The run ended with GPIO12 and GPIO13 both reported as `input`
and no remaining PWM thread. Output evidence is in:

- `.runtime/anti_drone_servo/hardware_summary.json`;
- `.runtime/anti_drone_servo/hardware_target_state.jsonl`.

The venv did not contain `lgpio`; the run used the already-installed system
`lgpio` module through a temporary `PYTHONPATH` overlay. No package was
installed or modified. This is an environment prerequisite for reproducing
the hardware mode.

## USB webcam runner

`/home/pitan/antidrone-servo-port/run_tracking.sh` is the normal live command.
It opens `/dev/video0`, displays the annotated OpenCV window on `DISPLAY=:0`,
and stops on `q` or `Ctrl+C` with GPIO cleanup. A bounded live check processed
63 USB-camera frames, recorded `input.type=USB_CAMERA`, and ended with both
GPIO12 and GPIO13 back in `input` state.
