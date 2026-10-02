# Scope 28 — Dual-Stream Design

`scope28-v1` is an adapter contract, not a detector-threshold replacement:

| Stream | Rule | Consumer |
|---|---|---|
| `FROZEN_PUBLIC_STREAM` | confidence >= 0.25 | frozen public detector semantics / equivalence evidence |
| `TRACKER_LOW_STREAM` | 0.10 <= confidence < 0.25 | existing ByteTrack second association stage |

The adapter performs one NCNN inference, restores boxes to original-frame coordinates, applies one NMS at IoU 0.70 to the floor-filtered candidates, then splits the kept rows. Confidence/class/box values are passed through unchanged. The tracker receives `high + low`; it still creates new tracks only from its unchanged `new_track_thresh=0.35` high path.

The production candidate package and Scope 25/26 artifacts remain untouched.
