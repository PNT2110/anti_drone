# Drone Detection Confidence Sweep — 2026-10-02

This preliminary, single-model sweep is superseded by
[`MODEL_CONFIDENCE_MATRIX_2026-10-02.md`](MODEL_CONFIDENCE_MATRIX_2026-10-02.md),
which adds manually reviewed boxes and a six-model 0.1–1.0 comparison.

## Decision

Keep the current video inference floor at `0.10`, keep `0.25` as the minimum confidence for creating a new track ID, and keep the three-frame track confirmation. Do not raise the global detector threshold based on these clips.

The sweep found that raising the detector floor reduced the number of boxes shown, but did not consistently improve track identity stability. On the outdoor vertical clip it reduced the maximum simultaneously tracked objects from three at `0.10`/`0.25` to two at `0.35`/`0.40` and one at `0.50`/`0.60`. The lower inference floor also supplies weak observations that can keep an already-confirmed track alive; tentative objects and boxes without an assigned ID are not shown.

## User-uploaded video sweep

The live server's three distinct uploaded input videos were evaluated with the fresh `drone-yolov8n-fresh-480.pt` checkpoint at `imgsz=960`. Each video was processed once by YOLO at `conf=0.10`; detections were then filtered at each sweep threshold and passed through an independent tracker configured with 4 s active timeout, 60 s appearance memory, 0.45 appearance re-ID threshold, 0.25 new-track confidence, and 3-frame confirmation. The shown-observation metric counts only boxes that received a track ID, matching the website's rendering behavior.

| Clip | Duration / dimensions | Conf | Shown observations | Unique IDs | Max simultaneous IDs | Tracks under 10 shown frames |
|---|---:|---:|---:|---:|---:|---:|
| Short close-up | 30.33 s / 576×894 | 0.10 | 903 | 1 | 1 | 0 |
| Short close-up | 30.33 s / 576×894 | 0.25 | 903 | 1 | 1 | 0 |
| Short close-up | 30.33 s / 576×894 | 0.60 | 901 | 1 | 1 | 0 |
| Indoor room | 86.17 s / 1024×576 | 0.10 | 8,170 | 6 | 4 | 0 |
| Indoor room | 86.17 s / 1024×576 | 0.25 | 7,583 | 5 | 4 | 0 |
| Indoor room | 86.17 s / 1024×576 | 0.35 | 6,945 | 8 | 4 | 0 |
| Indoor room | 86.17 s / 1024×576 | 0.60 | 3,663 | 5 | 4 | 0 |
| Outdoor vertical | 52.50 s / 576×1024 | 0.10 | 1,660 | 6 | 3 | 0 |
| Outdoor vertical | 52.50 s / 576×1024 | 0.25 | 1,421 | 6 | 3 | 1 |
| Outdoor vertical | 52.50 s / 576×1024 | 0.35 | 1,271 | 8 | 2 | 3 |
| Outdoor vertical | 52.50 s / 576×1024 | 0.40 | 1,206 | 4 | 2 | 0 |
| Outdoor vertical | 52.50 s / 576×1024 | 0.60 | 788 | 4 | 1 | 0 |

Lower confidence did not cause many short-lived displayed tracks under the three-hit rule. On the multi-drone clips, higher thresholds removed a material share of track observations and in some cases reduced the number of drones visible at once. Unique ID counts are only a fragmentation proxy; without identity ground truth they are not an ID-switch score.

## Labeled diagnostic clips

A separate sweep used three local 640×512 Halmstad sequences. At IoU 0.50, the best detector F1 varied by clip: sequence 001 scored 0.840 at `0.35`/`0.40`; sequence 002 had near-zero overlap at every tested threshold; sequence 003 scored 0.472 at `0.60`. Only sequence 001 has user-verified identity labels; sequences 002 and 003 have box labels but identity review is pending, and source/training disjointness is unverified. These clips therefore do not establish a universal confidence optimum or independent generalization.

## Limitations and follow-up

- The three uploaded website clips have no frame-level box or identity ground truth. The comparison is a tracker-visible noise/recall proxy, not precision, recall, IDF1, or a formal proof that re-entering drones keep the same physical identity.
- The model tested was YOLOv8n fresh 480 only; the threshold was not compared across the YOLO11/YOLO26 models.
- Contact sheets compare the same three timestamps at confidence thresholds 0.15, 0.25, 0.35, 0.45, and 0.60:
  - `artifacts/video_tests/confidence_sweep_20261002/28c72ed6347947279450066549beac46_in_confidence_contact.jpg`
  - `artifacts/video_tests/confidence_sweep_20261002/b10dbcf1668e4da8b765e3591e8bda59_in_confidence_contact.jpg`
  - `artifacts/video_tests/confidence_sweep_20261002/125cc9659c284f35a92d705df32f7d31_in_confidence_contact.jpg`
- Full sweep tables are retained locally in `artifacts/video_tests/confidence_sweep_20261002/uploaded_video_metrics.json` and `artifacts/video_tests/confidence_sweep_20261002/confidence_metrics.json` (uploaded clips and labeled diagnostic clips, respectively).
- Do not change the production threshold from this sweep alone. For a defensible accuracy decision, annotate drone boxes and persistent identities across entry/exit events in indoor and outdoor clips, then measure precision/recall, IDF1, ID switches, and fragmentation.
