# Scope 18 — Label preflight

Status: **PASS**

- Samples: `30227`
- Split counts: train `12142`, val `8237`, test `9848`
- Class counts: `{"0": 30227}`
- Empty labels: `0`
- Source objects: `30227`; unresolved: `0`
- Quarantine leakage: `0`
- Source-sequence overlap: `0`; candidate-prefix overlap: `0`

The preflight re-read source annotations, verified class `0`, repaired coordinates, split counts, quarantine exclusion, sequence/prefix disjointness, and persisted deterministic seed-42 representative samples for modality, size and boundary categories in `.runtime/scope18/label_preflight.json`.

No test label was used for training or model selection; test remains reserved for a later frozen evaluation.
