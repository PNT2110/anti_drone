# Scope 30 — Target Source

Halmstad V_DRONE_001.mp4 displayed on host HDMI-1 2560x1440; pipeline input remained physical USB webcam /dev/video0. A webcam snapshot during the run showed ceiling, so the target was not actually visible through the camera.

The Halmstad video was used only as a visual screen-presented diagnostic source; it was not passed to the detector. The accepted target-present gate was not achieved because the physical webcam view did not contain the monitor target.

## Scope 30R alignment attempt

The required single snapshot showed no monitor or video. The physical webcam therefore did not receive a target stimulus, and the accepted target session was not started.

## Scope 30R2 / Attempt 3

Halmstad `V_DRONE_001.mp4` was playing on the host HDMI monitor, but the physical webcam frame did not contain that monitor. The MP4 was not passed to the detector.

## Scope 30R2 / Attempt 4 — accepted source

Halmstad `V_DRONE_001.mp4` was displayed on the 2560x1440 HDMI-1 monitor. The detector input remained the physical USB webcam `/dev/video0`; the MP4 was never passed directly to NCNN.
