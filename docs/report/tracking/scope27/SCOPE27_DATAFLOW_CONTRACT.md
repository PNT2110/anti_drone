# Scope 27 — Data-flow contract

```text
offline video frame
  -> frozen NCNN preprocess/inference/decode/NMS
  -> Detection(box=xyxy pixels, confidence, class_id)
  -> existing bytetrack_motion_adaptive
  -> Track objects (observed or predicted)
  -> deterministic dry-run target selection
  -> DRY_RUN_ONLY command preview
```

Coordinate spaces:

- `DETECTOR_SPACE`: RGB 480×480 letterboxed tensor; raw output `[1,5,N]`.
- `SOURCE_FRAME_SPACE`: original OpenCV BGR frame, 640×512 pixels.
- `TRACKER_SPACE`: original-frame `xyxy` pixel boxes, passed to `Detection`.
- `TARGET_STATE`: original-frame bbox/center and observed/predicted state.

The adapter performs only schema/coordinate/timestamp propagation. It does not filter detections beyond the frozen detector output, run another NMS, merge boxes, or synthesize detections. Source timestamps are the locked 30 FPS frame timestamps and remained monotonic.
