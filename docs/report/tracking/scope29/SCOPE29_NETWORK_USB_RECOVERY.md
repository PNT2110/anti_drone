# Scope 29R — Network/USB Recovery

The user reported reconnecting/power-cycling the webcam. The host then verified the post-recovery identity: Jieli Technology USB Composite Device, `4c4a:4a55`, capture `/dev/video0`, metadata `/dev/video1`. No automatic USB reset, driver unbind/rebind, or reboot was performed.

Independent V4L2 gate: **PASS**, 250 consecutive MJPG 640x480 frames at requested 25 FPS, bounded command terminated normally. The earlier Scope 29 blocker and all rejected runs remain preserved in `SCOPE29_INITIAL_FINAL_REPORT.md` and `.runtime/scope29/`.
