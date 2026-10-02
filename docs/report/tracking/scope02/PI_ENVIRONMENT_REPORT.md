# Scope 02 Pi environment report

## Access status

No Raspberry Pi shell or hardware access was granted in this workspace.
Scope 02 therefore did not SSH, start a camera, install system packages, or
measure Pi CPU/RAM/temperature. Pi hardware validation is `BLOCKED — PI
HARDWARE ACCESS`.

The repository contains historical runtime evidence from an earlier Pi run:
`.runtime/pi-replay/ncnn/environment.json` records Linux aarch64, Python 3.13.5
and an RPi kernel. That file is retained evidence, not a fresh Scope 02 audit
of the current Pi state.

## Host validation environment

The safe local validation environment was `/tmp/anti_drone_scope01_venv`:

```text
OS: Linux x86_64
Python: 3.14.7
NumPy: 2.5.3 (host site package visible in the virtualenv)
OpenCV: 5.0.0
ONNX Runtime: 1.30.0
NCNN: 1.0.20260526
```

The host virtualenv ran the local tests and both host ONNX/NCNN replays. It is
not a Pi performance substitute.

## Requirements comparison

`requirements-pi.txt` requests NumPy `>=1.26,<2.3`, headless OpenCV,
ONNX Runtime, and architecture-conditional TFLite/NCNN packages. The local
Python 3.14 environment had no compatible NumPy `<2.3` wheel available during
setup, so its host NumPy 2.5.3 was used only in the temporary validation
virtualenv. No repository constraint was relaxed and no system package was
changed.

## Missing Pi measurements

OS/kernel, aarch64 confirmation, Python 3.11 compatibility, installed
requirements, available RAM/disk, CPU utilization, and temperature remain
`BLOCKED` until the user runs the supplied Pi runbook directly on the device.
