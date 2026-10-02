# Scope 04 — Identity Annotation Report

## Status

`IDENTITY ANNOTATION PENDING`

The MATLAB source provides one `DRONE` rectangle for each of 301 frames, but
does not provide an identity field. The converter therefore produces source
boxes only and does not assign `track_id=1` or copy tracker output into ground
truth.

| Quantity | Result |
|---|---:|
| Source boxes | 301 |
| Frames with source DRONE annotation | 301 |
| Frames with multiple DRONE boxes | 0 |
| Source identity IDs | 0 |
| Verified track IDs | 0 |
| Official identity GT rows | 0 |
| Official identity GT status | PENDING |

## Required human action

Review the overlay package and assign a stable physical-object ID only after
visually confirming continuity, disappearance/reappearance and any occlusion.
The output schema is:

```text
sequence_id,frame_id,track_id,class_id,x1,y1,x2,y2
```

`class_id` must be 0. The generated source-box provenance must remain beside
the reviewed file. Human review is not implied by the existence of the CSV or
the overlay.
