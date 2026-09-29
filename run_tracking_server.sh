#!/usr/bin/env bash
set -euo pipefail

# Main Pi runner: frozen anti-drone detector + ByteTrack tracking.
# Run this from a Raspberry Pi desktop terminal so the fullscreen OpenCV
# window is visible. This installed launcher enables the already-commissioned
# PAN/TILT hardware by default. Pass --dry-run to inspect detections without
# claiming GPIO or emitting PWM.
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export DISPLAY="${DISPLAY:-:0}"
export PYTHONPATH="/usr/lib/python3/dist-packages:${ROOT_DIR}/src:${ROOT_DIR}/scripts"

MODE_ARGS=(--hardware)
FORWARD_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) MODE_ARGS=() ;;
    --hardware) MODE_ARGS=(--hardware) ;;
    *) FORWARD_ARGS+=("$arg") ;;
  esac
done

v4l2-ctl -d /dev/video0 \
  --set-ctrl=brightness=0,contrast=256,saturation=256,gamma=20,gain=7,power_line_frequency=1,white_balance_temperature=4500,sharpness=128,backlight_compensation=0
v4l2-ctl -d /dev/video0 \
  --set-ctrl=auto_exposure=1,exposure_time_absolute=300
v4l2-ctl -d /dev/video0 \
  --set-fmt-video=width=1280,height=720,pixelformat=MJPG \
  --set-parm=25

exec "${ROOT_DIR}/venv/bin/python" \
  "${ROOT_DIR}/scripts/anti_drone_pi_servo_tracking.py" \
  --config "${ROOT_DIR}/config.json" \
  --camera /dev/video0 \
  --show \
  "${MODE_ARGS[@]}" \
  "${FORWARD_ARGS[@]}"
