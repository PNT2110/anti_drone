# Multi-Drone Persistent ID Tracking Report

## Executive conclusion

The required behavior is a multi-object tracking (MOT) problem, not a second
object-detection class. YOLO detects a drone in each frame; a tracker must then
associate detections over time. The best-performing tested architecture for
these clips is:

```text
fresh YOLO detector -> motion association -> chroma-aware appearance matching
                    -> short-term tracks + dormant identity gallery -> ID overlay
```

The web runtime uses a lightweight local tracker, with a 4-second active window
and a 60-second appearance gallery. On the indoor clip, Ultralytics BoT-SORT/ReID
produced 37 unique IDs and TrackTrack/ReID produced 27, versus 8 with the local
tracker; both built-in alternatives also took about 95--98 seconds for the
86-second clip. They were not promoted to production. The latest descriptor
reduces white-wall influence by normalizing hue over chromatic crop pixels, and
weak detections may continue existing tracks without creating IDs or polluting
the gallery.

## Latest deployment validation (2026-10-01)

The public web app exposes only the fresh training outputs: six `.pt`
checkpoints and `fresh_yolo26_img640_best.onnx`; legacy model files are not
listed or selectable through `/api/models`. The default is
`drone-yolov8n-fresh-480.pt`; uploaded-video inference uses 960 pixels because
the FPV targets occupy very few pixels in the source videos, with detector
confidence 0.10 for uploaded videos only. A detection below 0.25 can continue
an existing track, but cannot start an ID or update its appearance gallery. A sampled
comparison of all six checkpoints found YOLOv8n 480 gave the strongest indoor
detection coverage; the public outdoor clip was similar across all six. Tracker
defaults retain active tracks for 4 seconds and dormant appearance for 60
seconds, with a 0.45 re-identification threshold. Its hue histogram ignores
low-saturation background pixels and normalizes hue separately from saturation
and value. All seven primary local model files were SHA-256 checked against the
server copies.

Across six fixed indoor timestamps, raw detection counts summed to 21 for
YOLOv8n-480, 18 for YOLO11n-480, 15 each for YOLO26n-480 and YOLO26n-640, 13
for YOLOv8n-640, and 12 for YOLO11n-640. This favors YOLOv8n-480 for these
small indoor targets, but counts alone are not precision/recall because the
frames do not have hand-labeled boxes.

| Clip | Frames | Detector observations | Unique IDs | Review |
| --- | ---: | ---: | ---: | --- |
| Indoor multi-drone (`1790619048749_...mp4`) | 2,584 | 8,692 | 6 | Compared with the 0.15-confidence appearance-rescue run: 516 more detection observations and one fewer unique ID. Sampled frames show the large FPV retaining ID 2 through 25.8--77.4s and the red FPV retaining ID 4 through 25.8--77.4s, including a detection gap. |
| Outdoor (`1790705572852_...mp4`) | 644 | 1,227 | 2 | At confidence 0.10 the two visible drones still retain two IDs (7 additional observations vs. confidence 0.15). |

The indoor video is not considered a full pass. Six unique IDs may still
fragment identities among the roughly four drones visible in sampled frames,
and small or blurred targets are occasionally missed. The appearance fallback
fixes two specific observed continuity breaks, but samples cannot prove that
IDs never switch elsewhere in the 2,584-frame clip. Detection observations are
not labeled true positives, so a lower ID count is not a detection-accuracy
score. The final public-API outputs are
`artifacts/video_tests/1790619048749_fresh480_final.mp4` and
`artifacts/video_tests/1790705572852_fresh480_final.mp4`; the sampled audit
frames are under `artifacts/video_tests/review/final_audit/`.

The outdoor clip is a visual check, not a labeled benchmark. Neither video has
ground-truth boxes or physical-drone IDs, so these results cannot establish
precision, recall, IDF1, HOTA, or a formal detection-accuracy score. The
downloaded public-API outputs and review frames are under
`artifacts/video_tests/`.

## What was researched

- Ultralytics recommends BoT-SORT for moving-camera footage such as drone
  video. Its tracker supports camera-motion compensation and optional Re-ID;
  `persist=True` is required when processing consecutive frames from one
  stream. See [Ultralytics tracking documentation](https://docs.ultralytics.com/modes/track).
- Direct tests of current Ultralytics BoT-SORT/ReID and TrackTrack/ReID with
  the fresh YOLOv8n-480 detector on the indoor clip yielded 37 and 27 unique
  IDs, respectively, and took about 95--98 seconds. The local tracker yielded
  8 IDs in about 30 seconds in detector+tracker diagnostic runs, so these
  built-in alternatives are not the production choice for these videos.
- ByteTrack associates lower-confidence detections as well as high-confidence
  detections, which helps bridge brief occlusion and detector confidence dips.
  See [ByteTrack](https://arxiv.org/abs/2110.06864).
- BoT-SORT combines motion, appearance, camera-motion compensation and a
  stronger Kalman state for identity association. See
  [BoT-SORT](https://arxiv.org/abs/2206.14651).
- UAV tracking has additional viewpoint and disappearance problems. SeaDronesSee-MOT
  explicitly evaluates long-term re-identification after objects disappear and
  reappear; see [Sea You Later](https://openaccess.thecvf.com/content/WACV2024W/MaCVi/papers/Yang_Sea_You_Later_Metadata-Guided_Long-Term_Re-Identification_for_UAV-Based_Multi-Object_Tracking_WACVW_2024_paper.pdf).

## ID lifecycle used by this project

1. The first confirmed detection receives the next stream-local ID.
2. While visible, the ID is matched using predicted motion, IoU, center
   distance and the crop appearance descriptor.
3. During a short occlusion, the track remains active for 4 seconds.
4. Every unmatched track, including one still inside the active window, gets a
   second appearance-based association pass. Its appearance gallery remains
   available for up to 60 seconds.
5. A returning detection can reclaim the old ID only when its appearance is
   sufficiently close, its crop has enough visual quality, and it is clearly
   more plausible than other candidates. Position ranks candidates but is not
   a hard gate after a track is missed; an ambiguous lookalike still receives
   a new ID rather than a guessed resurrection.
6. A new video/camera stream resets the namespace. IDs are not promised to be
   globally stable across application restarts or unrelated cameras.

The implementation is in `web/backend/tracker.py` and is configured through
`configs/trackers/long_term_reid.yaml` or environment variables:

```text
ANTI_DRONE_ACTIVE_TRACK_TTL=4.0
ANTI_DRONE_REID_MEMORY_SECONDS=60.0
ANTI_DRONE_REID_MATCH_THRESHOLD=0.45
ANTI_DRONE_NEW_TRACK_MIN_CONFIDENCE=0.25
ANTI_DRONE_GALLERY_UPDATE_THRESHOLD=0.15
```

Uploaded videos currently use detector confidence 0.10; live camera paths keep
their existing defaults. The tracker creates a new ID only at confidence 0.25
or higher. An unmatched weak box stays available to the tracker but is hidden
from the rendered video; weak detections that continue a known track remain
visible with that track's ID.

## Important limitation

The current detection dataset is single-class (`drone`) and does not contain
identity labels for individual physical drones. A visual descriptor can keep
IDs stable in many re-entry cases, but no tracker can guarantee identity when
two drones look alike, the target is tiny/blurred, or the time gap is long.
For the highest reliability, collect short MOT sequences with per-drone IDs,
include indoor/outdoor lighting and FPV motion, and benchmark a learned Re-ID
embedding (BoT-SORT-ReID or Deep OC-SORT) against the lightweight tracker.

## Validation plan

Report these metrics separately for indoor, outdoor, single-drone and
multi-drone clips:

- IDF1 and HOTA: identity quality and tracking quality.
- ID switches and fragmentation: the direct failure modes for this request.
- Recall during occlusion and re-entry after 1, 5, 10 and 30 seconds.
- End-to-end FPS and memory use on the web server and Pi 5.

Eleven tracker unit tests cover long re-entry, fast displacement inside the
active TTL, ambiguous lookalikes, distinct-color crossings, stream isolation,
low-confidence handling and background-resistant appearance features. The
suite passes locally (11 passed; 7 model-engine tests skipped because those
model-dependent checks are unavailable in this environment).

## Review decision for the next tracking iteration

The current evidence supports this production direction:

```text
fresh YOLO detector -> lightweight motion association -> chroma-aware Re-ID
                    -> persistent stream-local identity gallery -> ID overlay
```

The runtime should keep two identifiers separate:

- `tracker_id`: a short-lived association generated by the MOT tracker.
- `global_identity_id`: the persistent stream-level identity shown to users.

The gallery is updated only from sufficiently large detections at or above the
new-track confidence floor, and appearance-discordant crops cannot poison it.
An appearance second pass now rescues motion-gate misses, including recent
tracks; re-entry requires an absolute similarity threshold and a margin over
the second-best candidate. Ambiguous matches still receive a new ID rather
than a confident but incorrect resurrection. Frame-level IDF1 and ID-switch
evaluation remains open until identity labels are available.

For the next benchmark, after collecting physical-identity labels, compare the
current lightweight tracker against:

1. ByteTrack as the low-cost baseline.
2. BoT-SORT without Re-ID.
3. BoT-SORT with Re-ID and camera-motion compensation.
4. BoT-SORT/Re-ID plus the persistent gallery used by this project.

The MOT split must be made by complete video or flight session, never by random
frames from the same clip. Add crossing, 3--5-drone congestion, occlusion,
indoor low light, outdoor sky, motion blur and exit/re-entry sequences. Besides
HOTA, IDF1, ID switches and fragmentation, report re-entry correct-ID rate,
false resurrection rate and crossing ID-switch rate. A single-class detector
dataset cannot train true physical identity by itself; those experiments need
per-drone MOT IDs and, ideally, a `physical_drone_id` field.
