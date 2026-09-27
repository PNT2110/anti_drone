# Live USB-camera runtime diagnosis

## Evidence from the failing hardware run

The inspected hardware run contained 3,140 frames. Only 27 frames reached
`OBSERVED`; 3,113 were `NO_TARGET`. The detector returned no candidate in
2,642 frames, while 342 frames had a HIGH candidate and 156 had LOW-only
candidates. The camera was visibly aimed at the ceiling for the latest frames,
so the dominant failure was loss of visual coverage rather than thermal or RAM
pressure. Raspberry Pi temperature was 56.0 C, throttling was `0x0`, and
3.3 GiB RAM remained available.

The old synchronous runtime achieved 16.32 FPS from timestamps. Its frame
interval was 61.29 ms mean, 57.77 ms p50, and 67.89 ms p95, with one 1.77 s
stall. It wrote two JPEGs every ten frames and another two JPEGs for every
detection frame. That blocking disk work was removed and snapshots are now
rate-limited to once per second.

The hardware path also used a generic 500--2400 us software-PWM conversion.
The configured tilt center of 120 degrees maps close to the upper pulse range,
and the observed camera pose was the ceiling. Physical actuation is therefore
no longer enabled by default in `run_tracking.sh`; `--hardware` is explicit
until the center, direction, and pulse limits are revalidated for the mounted
camera.

## Duplicate-box and identity cause

At close range the model produced a whole-visible-drone box and one or more
arm/rotor boxes. A representative pair had IoU about 0.62, so the fixed NMS
gate of 0.70 correctly retained both, although 82.8% of the smaller box
overlapped the larger box. ByteTrack then interpreted those boxes as separate
observations and repeatedly created motion IDs.

The live adapter now:

- keeps NMS exactly once at 0.70;
- removes strongly overlapping smaller part boxes using intersection over the
  smaller box;
- in declared `SINGLE_DRONE_SESSION` mode, passes at most one observation per
  frame, selected by `confidence * sqrt(area)`;
- gives HIGH precedence over LOW and uses LOW only when HIGH is absent;
- preserves public `DRONE ID 1` while retaining ByteTrack's internal IDs in
  logs.

In the final 840-frame dry-run, 811 frames were `OBSERVED`, every frame had a
HIGH observation, multi-detection frames fell to zero, and the only public ID
was 1. Thirteen internal reassociations remained during large pose/box changes;
these remain auditable and are not presented as physical ReID.

## Display and performance

The Pi display is now fullscreen with aspect-ratio-preserving pillar boxes,
rolling FPS, NCNN inference time, and tracker time. Representative fullscreen
operation measured approximately 13.6 FPS. NCNN dominated at roughly 42 ms
mean; tracker time was around 1 ms and was not the bottleneck. Fullscreen
composition and GUI presentation account for much of the remaining frame
time. The capture buffer is limited to one frame to reduce stale-camera lag.

The first fullscreen build still captured at 640x480 and enlarged that image
to the 1920x1080 display, which visibly magnified compression/pixelation. A
camera capability audit confirmed native MJPEG 1280x720 and 1920x1080 modes at
25/30 FPS, with no hardware zoom control. The runtime therefore uses
1280x720 MJPEG at 25 FPS: it matches the 16:9 display, exposes a wider
horizontal field than the camera's 640x480 mode, and avoids the extra decode
and display cost of 1920x1080 capture. Any remaining field-of-view limit is a
property of the physical lens, not a software crop or zoom setting.
