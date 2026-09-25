# Scope 27 — Detector adapter

The adapter is [`scope27_pi_dryrun.py`](../../../scripts/scope27_pi_dryrun.py). It consumes the frozen NCNN package and uses the existing Scope 21 preprocess/decode contract:

- BGR → RGB;
- `rect=False` letterbox, padding 114, 480×480;
- float32 `/255`, NCHW, batch 1;
- raw `[1,5,N]`, `xywh` plus class-0 score;
- confidence `0.25`, external NMS IoU `0.70` exactly once;
- restored `xyxy` boxes in original 640×512 frame space.

The adapter converts each final detection to the existing `anti_drone.tracking.Detection` type and passes it to the unchanged `ByteTrack` implementation. Scope 27 parity smoke: 8/8 `PARITY_PASS`, artifact hashes exact.
