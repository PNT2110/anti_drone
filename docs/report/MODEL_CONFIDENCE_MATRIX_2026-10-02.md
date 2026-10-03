# Drone model, confidence, and identity review — 2026-10-02

## Decision for the public web application

- Model: `drone-yolov8n-fresh-480.pt`.
- Video detector confidence floor: **0.10** at `imgsz=960`, NMS IoU 0.45.
- Tracker: keep a 0.25 minimum confidence for *new* IDs, three-frame confirmation, 4-second active timeout, 60-second dormant appearance memory, and 0.45 re-identification distance threshold.
- This is the best **single** model/confidence combination on the three reviewed videos. It is not a guarantee of perfect physical identity after occlusion, leaving the frame, or an edited shot.

The public SSH server at `100.121.224.18` was checked on 2026-10-02: the website process was running, `/api/models` reported `drone-yolov8n-fresh-480.pt` as active, and its video processing code defaults to confidence 0.10 and `imgsz=960`. These settings already matched the selected combination, so no service restart or model switch was necessary.

## Evaluation design

Six fresh checkpoints (YOLOv8n, YOLO11n, YOLO26n at both 480 and 640 training-image settings) were evaluated over three user-uploaded videos. The short clip has 905 frames, the four-drone indoor clip 2,584, and the outdoor clip 1,575: **5,064 frames per model**, or 30,384 model-processed frames in the full comparison. The model ran at inference size 960 in all cases. Each video was decoded once per model at confidence 0.10; detections were filtered independently at every confidence from **0.1 to 1.0 in steps of 0.1** and passed to separate tracker instances. Only confirmed, displayed boxes were scored.

Eight frames per clip were manually reviewed, with **47 drone boxes across 24 sampled frames**. Box matching used IoU 0.30 and 0.50. The selection score is the mean of the per-clip F1 values at both IoU cutoffs, so no single video dominates only because it contains more drones. The reviewed boxes are approximate manual annotations. These videos are not a disjoint benchmark; their relationship to training data is unverified. The scores are diagnostic for these clips, not generalized model accuracy.

## Best confidence for each model

| Model | Best confidence | Mean F1 @ IoU .30 | Mean F1 @ IoU .50 | Combined | TP / FP / FN @ .30 | Indoor recall @ .30 | Reviewed ID changes |
|---|---:|---:|---:|---:|---:|---:|---:|
| YOLOv8n fresh 480 | **0.1** | **0.846** | **0.821** | **0.834** | 34 / 1 / 13 | **0.688** | 7 |
| YOLOv8n fresh 640 | 0.1 | 0.831 | 0.805 | 0.818 | 32 / 1 / 15 | 0.625 | 8 |
| YOLO11n fresh 640 | 0.1 | 0.823 | 0.797 | 0.810 | 31 / 1 / 16 | 0.594 | 6 |
| YOLO26n fresh 640 | 0.1 | 0.810 | 0.797 | 0.803 | 30 / 2 / 17 | 0.563 | 9 |
| YOLO26n fresh 480 | 0.1 | 0.817 | 0.744 | 0.780 | 33 / 2 / 14 | 0.656 | 8 |
| YOLO11n fresh 480 | 0.4 | 0.737 | 0.722 | 0.730 | 24 / 1 / 23 | 0.406 | 6 |

The extra ID changes in the highest-scoring model are real limitations, but selecting YOLO11n solely for one fewer change on sparse reviewed frames would sacrifice drone recall. ID continuity is a tracker/re-identification problem, not something that can be fixed just by raising detector confidence.

## Exact 0.1–1.0 confidence sweep for the selected model

| Confidence | Combined mean F1 | TP / FP / FN @ IoU .30 | Indoor recall @ .30 | Reviewed ID changes |
|---:|---:|---:|---:|---:|
| **0.1** | **0.834** | **34 / 1 / 13** | **0.688** | 7 |
| 0.2 | 0.796 | 32 / 1 / 15 | 0.656 | 7 |
| 0.3 | 0.780 | 30 / 1 / 17 | 0.594 | 8 |
| 0.4 | 0.743 | 26 / 1 / 21 | 0.469 | 3 |
| 0.5 | 0.722 | 24 / 1 / 23 | 0.406 | 4 |
| 0.6 | 0.558 | 18 / 1 / 29 | 0.313 | 1 |
| 0.7 | 0.348 | 11 / 1 / 36 | 0.156 | 1 |
| 0.8 | 0.000 | 0 / 0 / 47 | 0.000 | 0 |
| 0.9 | 0.000 | 0 / 0 / 47 | 0.000 | 0 |
| 1.0 | 0.000 | 0 / 0 / 47 | 0.000 | 0 |

At 0.1, the reviewed short, indoor, and outdoor clips respectively gave 6/1/2, 22/0/10, and 6/0/1 TP/FP/FN at IoU 0.30. Raising confidence lowers apparent ID changes largely by suppressing drones entirely; it is not a genuine identity improvement. Confidence 1.0 is an exact threshold in the sweep and predictably produces no detections.

## Identity continuity audit

The website assigns a stream-local ID after three detector-supported frames. Motion association continues visible tracks; appearance matching can revive a dormant track for up to 60 seconds. The same ID does **not** persist across separate video uploads or camera sessions by design.

At confidence 0.1, manually distinguishable objects had **0** reviewed ID changes on the short clip, **5** indoors, and **2** outdoors. The indoor video reached four simultaneously displayed IDs, but had six unique IDs across its duration. The outdoor clip had only one physically reviewed drone, yet six unique displayed IDs over the full video. Therefore the current tracker **does not reliably remember the same physical drone** throughout every cut, long disappearance, or large appearance change. The review frames are sparse; this is not an IDF1/MOTA measurement and cannot establish exact event-level re-entry accuracy.

Ten tracker configurations were compared on the same detections, changing active timeout, appearance gate/weight, and re-ID threshold. The baseline had seven reviewed changes. A 6-second active timeout reduced this to six but increased outdoor unique IDs from six to seven; 1- and 2-second timeouts increased reviewed changes to 13 and 12. Appearance and re-ID threshold adjustments did not improve the overall continuity. The baseline is retained rather than tuning aggressively to three clips.

## Reproducible artifacts and next validation

- Raw full-video scores for all six models and all ten confidences: `artifacts/video_tests/model_conf_20261002/results/full_video_matrix/*.json`.
- Manual box labels: `artifacts/video_tests/model_conf_20261002/manual_labels.csv`.
- Tracker parameter trial: `artifacts/video_tests/model_conf_20261002/results/full_video_matrix/tracker_configurations.json`.
- Three source clips: `artifacts/video_tests/source_clips_20261002/`.
- Three annotated videos with visible boxes and IDs: `artifacts/video_tests/model_conf_20261002/selected_output/*_tracked.mp4`.
- Evaluation/render code: `scripts/evaluate_model_confidence_matrix.py`, `scripts/evaluate_full_video_matrix.py`, `scripts/evaluate_tracker_configurations.py`, and `scripts/render_selected_drone_videos.py`.

For a defensible persistent-ID claim, label identities densely across full entry/exit and occlusion events, keep the evaluation videos disjoint from training, and then measure IDF1, identity switches, false tracks, precision, and recall. A drone-specific learned re-identification embedding could then be trained or adapted and tested against the present color/shape tracker. Without distinguishing visual evidence, two identical drones that disappear and return cannot be assigned their original identities with certainty from video alone.
