# Scope 26 — Final report

## Final status

**`FINAL_TEST_COMPLETE`**

## Required answers

1. Freeze manifest hash: **MATCH**, `e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964`.
2. Candidate/package hashes: **MATCH**; candidate `scope18-yolov8n-480:ncnn`, NCNN param/bin exact.
3. First TEST-open timestamp: `2026-09-25T19:12:40.602499+00:00`.
4. TEST coverage: expected `9848`, processed `9848`, skipped `0`.
5. Precision: `0.939391`.
6. Recall: `0.873477`.
7. mAP50: `0.867244`.
8. mAP50-95: `0.477652`.
9. Visible: precision `0.952722`, recall `0.908583`, mAP50 `0.897849`, mAP50-95 `0.515558`.
10. Infrared: precision `0.925869`, recall `0.839617`, mAP50 `0.827215`, mAP50-95 `0.436674`.
11. Object size: recall `0.825157` for 16–32 px, `0.837538` for 32–64 px, and `0.914606` for >64 px; AP by size is N/A under the declared evaluator.
12. Error counts: headline TP/FP/FN `8602/555/1246`; error-analysis events FALSE_NEGATIVE `1096`, FALSE_POSITIVE `399`, LOCALIZATION_ERROR `306`. Below-threshold and NMS-interaction causes are not observable from retained output.
13. Changes after TEST: **none**. No threshold, model, backend, preprocessing, postprocessing, or runtime contract was changed.
14. Headline result SHA-256: `7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83`.
15. Regression tests: `126 passed, 1 skipped`; compileall PASS; `git diff --check` PASS. No TEST rerun is involved.
16. `SESSION_DISJOINT`: **UNVERIFIED**.
17. Final status: **`FINAL_TEST_COMPLETE`**.

## Scope boundaries

The primary headline comes only from the frozen Scope 25 NCNN package running on the Raspberry Pi 5. No PyTorch, ONNX, INT8, alternate model, retraining, split change, tracker, camera, or servo work was used. The result is a final evaluation of this protected V3 TEST split; it does not prove universal real-world drone generalization. Old V1 checkpoint status remains `SPLIT_UNVERIFIED` and was not used as a fair comparison.
