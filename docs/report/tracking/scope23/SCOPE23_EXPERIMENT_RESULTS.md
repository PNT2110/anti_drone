# Scope 23 — Experiment results

All three declared corrective experiments were executed on host using the fixed 8-image set and deterministic secondary 32-image TRAIN set.

| Experiment | Candidate | Fixed-8 count mismatch | Fixed-8 min IoU | Fixed-8 max conf | Secondary-32 count mismatch | Secondary-32 min IoU | Secondary-32 max conf | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| E1 | scope18-yolov8n-480 | 7 | 0.677969 | 0.035638 | 24 | 0.347985 | 0.198680 | HOST_INT8_PARITY_FAIL |
| E1 | scope18-yolov8n-640 | 3 | 0.757873 | 0.071762 | 14 | 0.382176 | 0.230079 | HOST_INT8_PARITY_FAIL |
| E2 | scope18-yolov8n-480 | 8 | 0.488754 | 0.045657 | 21 | 0.343551 | 0.126539 | HOST_INT8_PARITY_FAIL |
| E2 | scope18-yolov8n-640 | 4 | 0.720617 | 0.049889 | 18 | 0.345223 | 0.133605 | HOST_INT8_PARITY_FAIL |
| E3 | scope18-yolov8n-480 | 1 | 0.820101 | 0.120794 | 2 | 0.757549 | 0.146094 | HOST_INT8_PARITY_FAIL |
| E3 | scope18-yolov8n-640 | 1 | 0.850118 | 0.251138 | 6 | 0.513572 | 0.283404 | HOST_INT8_PARITY_FAIL |

No primary candidate passed. E2 was not an improvement over E1; E3 was the strongest bounded result but still failed the frozen gate.
