# Live-camera detector accuracy research plan

## Current diagnosis

The stage-3 model recognizes the actual drone, including close and clipped
views, but the live evidence reveals two dataset weaknesses:

1. Twenty-six fresh USB frames were repeated into 1,248 training records.
   Repetition increased weight but not visual diversity, so it can reinforce
   one room/view without teaching robust boundaries.
2. The deployed room contains hard look-alikes: fan blades, chair arms, cables,
   box edges, and partial high-contrast structures. The training set does not
   yet contain enough unique, empty frames from those exact conditions.

The current single-drone adapter fixes duplicate tracking observations, but it
does not make detector metrics better. Accuracy improvement must be measured
on a held-out live-camera validation set.

## Recommended experiment, in order

### 1. Build a target-domain dataset with unique frames

Capture separate sessions covering:

- close, medium, and far distances;
- centered and all four image edges;
- full drone, partially clipped drone, and partial occlusion;
- front/side/top/diagonal attitudes;
- stationary and moving drone/camera, including realistic motion blur;
- bright, dim, backlit, and mixed indoor lighting;
- at least three materially different rooms/backgrounds, with one entire
  environment reserved as an unseen holdout.

Use temporal/perceptual de-duplication instead of repeating the same 26 frames.
Label the whole visible drone consistently; never label an arm or rotor as a
separate drone. Split by capture session so adjacent video frames cannot leak
between train and validation. A random image split is insufficient because
nearby frames share the same background and appearance.

### 2. Mine hard negatives from the real camera

Run the current model on long no-drone USB videos and save deterministic
false-positive frames, including ceiling, fan, chair, cables, boxes, shadows,
and the pan/tilt mount. Add those as empty-label TRAIN images after human
verification. Keep a disjoint no-drone session for validation and report false
positives per minute. Video-based hard-negative mining is specifically useful
because detector flicker exposes recurring false-positive phenomena
([ECCV 2018 paper](https://openaccess.thecvf.com/content_ECCV_2018/papers/SouYoung_Jin_Unsupervised_Hard-Negative_Mining_ECCV_2018_paper.pdf)).

### 3. Run controlled fine-tuning, not blind continuation

Create a new candidate rather than overwriting the current model. Start from
the selected stage-3 checkpoint, use a lower learning rate, deterministic
seeds, and early stopping against the new session-disjoint live validation.
Compare a small matrix:

- baseline 480;
- 480 with unique target-domain positives plus hard negatives;
- the same data with moderate scale/rotation/perspective, brightness and blur;
- one 640 experiment only if far-drone recall remains poor.

Use Mosaic for scale/context diversity but disable it for the final epochs via
`close_mosaic`; Ultralytics documents both its small-object benefit and the
need to close it near training completion
([augmentation guide](https://docs.ultralytics.com/guides/yolo-data-augmentation)).
Avoid aggressive crops that turn a rotor or arm into an apparent complete
drone without a consistent label.

### 4. Freeze evaluation criteria before training

For every candidate report, on the same held-out live validation:

- precision, recall, mAP50, mAP50-95, and AP75;
- fixed-threshold TP, FP, FN, and F1 at confidence 0.25 / NMS 0.70;
- false positives per minute on no-drone video;
- recall by close/medium/far, clipped/unclipped, edge/center, and lighting;
- metrics per environment plus the fully unseen-environment holdout;
- duplicate boxes per positive frame;
- NCNN parity and Pi latency/FPS.

Ultralytics validation exposes mAP, per-image TP/FP/FN, PR curves, and
small/medium/large metrics; its documentation also notes that summary
precision/recall can use a max-F1 operating point, so fixed-threshold numbers
must be reported separately
([validation guide](https://docs.ultralytics.com/modes/val),
[metrics guide](https://docs.ultralytics.com/guides/yolo-performance-metrics)).

Do not select a confidence threshold by watching the same live session used
for validation. Preserve a final untouched target-domain session.

### 5. Treat far-drone enhancement as a separate latency experiment

Sliced inference can improve small-object AP by making tiny objects occupy
more pixels, and the SAHI paper reports AP improvements on small-object
datasets ([SAHI paper](https://arxiv.org/abs/2202.06934),
[implementation guide](https://github.com/obss/sahi/blob/main/docs/guides/sliced-inference.md)).
It is not the first choice here: multiple tile inferences would likely reduce
the current 13--17 FPS substantially on Pi 5. Evaluate it offline only if the
new 480/640 training still misses far drones, then consider an adaptive
periodic search rather than slicing every live frame.

## Acceptance proposal

A new model should replace the current live candidate only if it simultaneously:

- improves held-out live precision and recall;
- materially lowers false positives per minute;
- does not regress clipped/close detection;
- keeps precision/recall within the predeclared tolerance on an environment
  that contributed no frames to training or tuning;
- produces at most one whole-drone box in the single-drone scenario after the
  unchanged adapter contract;
- passes NCNN parity;
- retains an acceptable Pi end-to-end FPS and thermal profile.

V3 TEST must not be reused for this tuning loop. The new live-camera sessions
need their own group/session-disjoint train, validation, and final holdout.
