# Scope 25R — Test and regression report

Scope 25R did not access V3 TEST. The fixed smoke set contained 8 TRAIN images only.

Commands and results:

```text
python -m pytest -q                         122 passed, 1 skipped
python -m compileall -q scripts src tests    PASS
git diff --check                             PASS
```

The Scope 25 guards cover the exact candidate and hashes, 480/`rect=False`/padding 114 preprocessing, confidence `0.25`, NMS IoU `0.70`, one external NMS, FP32 NCNN, TEST exclusion, package/freeze-manifest hash validation, retention of non-selected artifacts, and tracker configuration presence.
