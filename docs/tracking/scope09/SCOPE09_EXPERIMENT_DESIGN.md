# Scope 09 — Experiment Design

## Question

This is a sensitivity study of the existing association Mahalanobis gate on one replayed sequence. It does not select a production value and does not establish generalization.

## Fixed design

Profiles: `bytetrack_motion` and `bytetrack_motion_adaptive`. `bytetrack_legacy` is retained as a Scope 07/08 reference and is not rerun here. Each profile was reset and replayed independently on the same 301 cache records in the same frame/timestamp order.

The only experimental variable was `adaptive_mahalanobis_gate ∈ {16, 25, 36}`. The production default is 25.0. Other effective values included detector confidence floor 0.1, low/high thresholds 0.1/0.25, new-track threshold 0.35, IoU match threshold 0.30, adaptive center gate 2.5, process/measurement noise 1.0/4.0, minimum confirmation 2, lost timeout 0.6 s, and reset gap 1.0 s.

GT matching is fixed box IoU with threshold `>= 0.50`, selecting the highest-IoU observed tracker box per frame. “Observed” means an observed tracker box meets that threshold. “Predicted-only” means no observed GT match while an active predicted track exists. “Lost” means neither condition holds. An ID change is a change between consecutive GT-matched observations. Latency is measured around `tracker.update` only; it is not end-to-end detector latency.

Alerts were replayed with the existing Scope 07/08 alert configuration. Prediction-only tracks are not observations and must not create alerts. Duplicate source-frame alerts are counted as an invariant check.

## Required control

Gate 25 was compared frame-by-frame with the stored Scope 08 instrumented output. Both profiles passed 301/301 frames. Any mismatch would have failed the run.

Artifacts are under `.runtime/scope09/`; no tracker, checkpoint, training, split, threshold or production configuration was changed.
