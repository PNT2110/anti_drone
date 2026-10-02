# Scope 07 — Final Report

## Final status

`COMPLETE — SINGLE-SEQUENCE DIAGNOSTIC; NOT AN INDEPENDENT TEST`

The three existing tracker profiles were replayed on the identical
`V_DRONE_001` detection cache and the Scope 06 human-verified ID 1 ground
truth. The result is diagnostic evidence for this sequence only. Data
independence remains `SPLIT_UNVERIFIED`.

## Findings

- Input audit: `PASS`; 301 manifest frames, 301 GT rows, 301 cache records.
- Cache detections: 272/301 frames; the 29 missing-detection frames were not
  repaired or removed.
- Matching: maximum bbox IoU, fixed threshold `0.50`, declared before replay.
- `bytetrack_legacy`: 258 observed GT frames, 33 predicted-only, 10 lost,
  2 created IDs, 1 ID change, 6 alerts, mean tracking-only latency 0.011879 ms.
- `bytetrack_motion`: 255 observed GT frames, 40 predicted-only, 6 lost,
  7 created IDs, 6 ID changes, 8 alerts, mean 0.145520 ms.
- `bytetrack_motion_adaptive`: 255 observed GT frames, 31 predicted-only,
  15 lost, 5 created IDs, 4 ID changes, 6 alerts, mean 0.124815 ms.
- Prediction-only alerts: 0 for all profiles. Duplicate source-frame alerts:
  0 for all profiles.
- HOTA/IDF1/IDSW: `N/A`; no approximate metric was substituted.

These numbers do not establish which profile generalizes better. The sequence
contains one labeled physical drone and cannot test simultaneous-drone
identity competition or cross-target association.

## Reproduction and artifacts

```text
python scripts/run_scope07_diagnostic.py
python -m pytest -q
```

Detailed report: [SCOPE07_TRACKING_REPORT.md](SCOPE07_TRACKING_REPORT.md)

Artifacts:

- `.runtime/scope07/input_audit.json`
- `.runtime/scope07/SCOPE07_BENCHMARK.json`
- `.runtime/scope07/bytetrack_legacy.jsonl`
- `.runtime/scope07/bytetrack_motion.jsonl`
- `.runtime/scope07/bytetrack_motion_adaptive.jsonl`

Output checksums:

```text
978038e27668a0bb977a5cbdc4966fae5a34667ba21435510ed76752ac4d8c87  .runtime/scope07/input_audit.json
a564bc44b706c8106db7133666cc1696a21379de466dce0f63fa182e60852c0b  .runtime/scope07/SCOPE07_BENCHMARK.json
8f03e2390250485cd131ac78372aa0cd864b82229e0ea0afc093bedfa1e8e52f  .runtime/scope07/bytetrack_legacy.jsonl
25411fbfd49bf20a0fe7b34859f5242ad65584701f4ec68b790c13e2c8797cc7  .runtime/scope07/bytetrack_motion.jsonl
8802d5d422e06e49a57fb6f1472133f90eadc15e8bf09fdeda0c31c03109d293  .runtime/scope07/bytetrack_motion_adaptive.jsonl
```

## Boundaries preserved

No tracker algorithm, threshold, checkpoint, dataset split, YOLO training,
detector rerun, Pi/camera runtime, or alert threshold was changed. No Git
commit or push was performed. `SPLIT_UNVERIFIED` is retained.
