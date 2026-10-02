# Scope 08 — Final Report

## Final status

`COMPLETE — ROOT-CAUSE AND ALERT AUDIT; SINGLE SEQUENCE ONLY`

Input integrity passed, all Scope 07 ID-switch events have replayable trace
evidence, and the alert invariant passed. No tracker algorithm was changed.
`SPLIT_UNVERIFIED` remains unchanged.

## Answers to the required questions

1. **Frame 53?** Motion and motion-adaptive received a real high-confidence
   detection, but association was rejected by the Mahalanobis gate (`30.110
   > 25`); a new ID was created. Category `C`.
2. **Frame 121?** A real detection was present. Motion failed both IoU and
   Mahalanobis gates; adaptive failed the Mahalanobis gate (`28.526 > 25`).
   Category `C`.
3. **Frame 158?** Profile-specific. Legacy created ID 2 at frame 151 after
   association failure and lifecycle removal of ID 1; frame 158 is when ID 2
   first crossed GT IoU 0.50. Motion created ID 4 at frame 154 after gate
   failure and removal of ID 3; frame 158 is likewise the GT-IoU crossing.
   Neither is a detector miss at frame 158.
4. **Frames 184 and 242?** Motion frame 184 is association failure against a
   still-LOST ID 4, then ID 5 is created. Adaptive frame 184 follows lifecycle
   removal of ID 3, so ID 4 is created with no active predecessor. At frame 242,
   both motion profiles reject a real high-confidence detection because
   Mahalanobis is `27.485 > 25`, creating a new ID.
5. **Motion frame 292?** A real high-confidence detection exists and overlaps
   GT at `0.807`, but association IoU is approximately `0.300` and is rejected
   by the existing 0.30 gate; ID 7 is created. Category `C`.
6. **Legacy alert frame 153?** Yes, it has a real observed detection on track
   2. It is not GT-matched at IoU 0.50, but three tracker observations satisfy
   the unchanged alert policy.
7. **Motion alert frame 156?** Yes, it has a real observed detection on track
   4. It is not GT-matched at IoU 0.50, but the prior two observations satisfy
   the high-confidence requirement.
8. **Prediction-only alert violation?** No. All profiles produced 0
   prediction-only alerts and 0 duplicate source-frame alerts.
9. **Implementation bug or current behavior?** No alert implementation bug was
   confirmed. The apparent Scope 07 ambiguity was a distinction between
   tracker observation and GT IoU match. ID events are existing association /
   lifecycle behavior under the current fixed configuration; no improvement
   is implemented here.
10. **Research & Design follow-up?** Consider a separately designed study of
    motion-gate calibration, lifecycle retention, and reporting semantics.
    Scope 08 does not select a better tracker or claim generalization.

## Reproduction and artifacts

```text
python scripts/run_scope08_audit.py
python -m pytest -q
```

- [SCOPE08_INPUT_AUDIT.md](SCOPE08_INPUT_AUDIT.md)
- [SCOPE08_ID_SWITCH_ROOT_CAUSE.md](SCOPE08_ID_SWITCH_ROOT_CAUSE.md)
- [SCOPE08_ALERT_EVENT_AUDIT.md](SCOPE08_ALERT_EVENT_AUDIT.md)
- [SCOPE08_TEST_REPORT.md](SCOPE08_TEST_REPORT.md)
- `.runtime/scope08/SCOPE08_AUDIT_SUMMARY.json`
- `.runtime/scope08/id_switch_events.csv`
- `.runtime/scope08/bytetrack_legacy.jsonl`
- `.runtime/scope08/bytetrack_motion.jsonl`
- `.runtime/scope08/bytetrack_motion_adaptive.jsonl`

Final artifact checksums:

```text
be9ee2f9a03e3585a808db039815fea9e725cf6fc17ca6347c8253c0f43292b7  .runtime/scope08/input_audit.json
b68e17d911dbda809c43fc8d4a500fc62f88ecf1b0cb38511effc65198b29028  .runtime/scope08/SCOPE08_AUDIT_SUMMARY.json
4025c9fafe867969c8cb2c2378f33a325f7603d3763dfe3f081331aa9f734402  .runtime/scope08/id_switch_events.csv
cee8954ba95c3ef11366fa3f7a38c39f252c5715a45f644e616402ce35081f2b  .runtime/scope08/bytetrack_legacy.jsonl
aae09d4e69a338a67ee0d6cf1ac667ec55866bbc8e4aaf011d58f8efb6483877  .runtime/scope08/bytetrack_motion.jsonl
746e9a149a005c6afbf9230132ef49a4e3efca2bc01904553d9aaa713bfee962  .runtime/scope08/bytetrack_motion_adaptive.jsonl
```

## Boundaries preserved

No detector rerun, detection repair, GT replacement, Kalman change, association
change, threshold change, lifecycle change, alert threshold change, new
tracker, training, dataset split, Pi/camera access, Git commit, or Git push was
performed. `SPLIT_UNVERIFIED` is retained.
