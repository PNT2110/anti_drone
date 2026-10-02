# Scope 09 — Final Report

Status: **PASS — completed as a bounded offline diagnostic.**

The study replayed the fixed Halmstad `V_DRONE_001` detection cache over 301 frames for `bytetrack_motion` and `bytetrack_motion_adaptive` at exactly gates 16, 25 and 36. Inputs were audited first, ground truth validation was already PASS, and no detector, tracker source, checkpoint, threshold, dataset split, Pi/camera or production YAML was changed.

The gate-25 control reproduced Scope 08 exactly for both profiles (301/301 frames each). The six requested event frames were exported with association and lifecycle evidence. Prediction-only tracks generated no alerts, and no duplicate source-frame alerts were observed.

The observed sequence is sensitive to the gate: wider gating can preserve an incumbent at some Mahalanobis-boundary events and reduce ID creation in this replay, while fixed IoU and lifecycle behavior remain confounding causes at other events. These results do not select a production gate, establish superiority, or support generalization beyond this single sequence. HOTA/IDF1 were not computed because this scope is a diagnostic gate study, not an independent benchmark.

Artifacts:

- Input audit: `.runtime/scope09/input_audit.json`
- Results: `.runtime/scope09/SCOPE09_RESULTS.json`
- Event table: `.runtime/scope09/event_analysis.csv`
- Six full traces: `.runtime/scope09/*_gate*.jsonl`
- Reports: this directory under `docs/tracking/scope09/`

Reproduction:

```bash
python scripts/run_scope09_gate_sensitivity.py
python -m pytest -q
```

Project status remains `SPLIT_UNVERIFIED`. No Git commit or push was performed.
