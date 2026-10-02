# Scope 04 — Test Report

## Result

`PASS`

The full regression suite completed with **30 passed, 0 failed, 0 skipped**.

Coverage added for Scope 04:

- MATLAB v5/MCOS sidecar parsing and `gTruth` field discovery;
- 301-row frame alignment and timestamp correspondence;
- `xywh` to `xyxy` conversion and source provenance;
- rejection of a one-frame offset;
- cross-split group/near-frame leakage detection;
- existing validator checks for invalid boxes, duplicate track IDs and missing
  identity annotation.

Additional checks:

```text
compileall scripts src tests       PASS
git diff --check                    PASS
source overlay video decode        PASS, 301 frames
source-box conversion              PASS, 301 rows
```

HOTA, IDF1 and IDSW were not run.
