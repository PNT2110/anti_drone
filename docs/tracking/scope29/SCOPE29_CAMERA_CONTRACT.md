# Scope 29 — Camera Contract

Selected mode: `/dev/video0`, MJPG, 640x480, requested 25 FPS. This is a source-frame contract; NCNN still receives BGR -> RGB, rect=False LetterBox, padding 114, 480x480, float32/255, NCHW.

Scope 28 dual stream is unchanged: public HIGH >=0.25, tracker LOW 0.10–<0.25, one inference and one NMS at IoU 0.70. Tracker profile/config remains `bytetrack_motion_adaptive`.

Capture uses a bounded queue of size 1 with `drop_stale_keep_newest`; all queue drops, read failures, and invalid dimensions are counted.
