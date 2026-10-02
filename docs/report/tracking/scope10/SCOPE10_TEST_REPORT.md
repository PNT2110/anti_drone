# Scope 10 Corrective — Test Report

Scope-specific validator tests cover:

- duplicate sequence IDs;
- same source-member/video collision;
- exact duplicate frame leakage as a separate class;
- provenance unknown and forbidden independent-validation permission;
- confirmed source-disjoint permission rules;
- non-monotonic timestamps;
- frame/annotation alignment and bounds;
- multi-object annotation rows.

Corrective V2 tests additionally cover:

- same-video frames and visible/infrared rows staying in one group;
- independent video groups remaining distinct;
- unknown provenance being quarantined;
- fixed-seed assignment reproducibility;
- sample accounting and V1 preservation;
- independent audit detection of an intentionally split verified group.

Commands:

```bash
python -m pytest -q tests/test_scope10_validation.py
python -m compileall -q scripts src tests
git diff --check
python -m pytest -q
```

The detector-cache preparation status is **BLOCKED** only because `cv2` is unavailable in this host. No cache or tracker benchmark was substituted. The existing OpenCV-dependent runtime test is reported as SKIPPED by the full suite rather than being weakened.

Final result: **corrective Scope 10 tests 12 passed**; the final full-suite result is recorded in `SCOPE10_FINAL_REPORT.md`. `compileall` and `git diff --check` also passed.
