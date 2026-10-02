# Scope 10 Corrective — Final Report

Status: **PARTIALLY COMPLETE — GROUP-DISJOINT V2 PASS; PROVENANCE NOT FULLY SOURCE-DISJOINT**.

1. **Missed requirement:** the original Scope 10 prepared temporal sequences and provenance artifacts but did not create or independently audit Group-Disjoint Dataset Split V2.
2. **045 versus 051:** archive listing confirms both member pairs. The actual repository currently contains `sequence_004/source/V_DRONE_045*`; `V_DRONE_051*` is absent from `data/tracking_eval/`. The stale report sentence was corrected; no video was renamed or replaced.
3. **Verified groups:** 318 `base:RGBT_*` sequence groups.
4. **GROUP_UNVERIFIED:** 4,172 groups and 6,505 samples, including `my_dataset` and prepared DUT/fallback rows.
5. **Samples:** train 21,168; val 6,096; test 2,963; quarantine 6,505. All 36,732 source samples are accounted for.
6. **Ratios over assigned samples:** train 70.0301%, val 20.1674%, test 9.8025%; approximate because groups remain intact.
7. **Verified group overlap:** 0.
8. **Exact source path/hash overlap:** 0 / 0.
9. **Reproducibility:** same seed 42 and algorithm version reproduced the V2 manifest and registry byte-for-byte in a temporary rebuild.
10. **V1 preservation:** unchanged hashes:

```text
3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d  data/processed/drone-single-class/manifest.json
7bc14c2e05b690f2df6c0cfb92e03b565a200f16dd0ef110df8e464837a63a54  data/processed/drone-single-class/split_registry.json
f25e3b3e199befecc325e6750cba1f81299e103042a3170618ae09f1ec6e06b2  data/processed/drone-single-class/audit.json
45c1f50e917b6a2c1b235d019ad33fceb1bbe9c82b4b770705656647e79fe49f  data/processed/drone-single-class/data.yaml
```

11. **Tests:** corrective V2 tests 12 passed; final full suite **62 passed, 1 skipped**. The skip remains the existing OpenCV-dependent runtime test because `cv2` is unavailable. `compileall` and `git diff --check` passed.
12. **Approval conditions remaining:** establish durable source-to-training provenance for the quarantined 6,505 samples, decide whether to review/obtain independent sequence identities, and explicitly approve V2 for a future training run. V2 is not activated and the V1 checkpoint remains a V1 checkpoint.

V2 artifacts:

- [manifest.json](/run/media/pnt/APP/anti_drone/data/processed/drone-single-class-v2/manifest.json)
- [split_registry.json](/run/media/pnt/APP/anti_drone/data/processed/drone-single-class-v2/split_registry.json)
- [audit.json](/run/media/pnt/APP/anti_drone/data/processed/drone-single-class-v2/audit.json)
- [output_checksums.json](/run/media/pnt/APP/anti_drone/data/processed/drone-single-class-v2/output_checksums.json)

No YOLO training, checkpoint replacement, tracker/gate change, Pi/camera access, source-image modification, or Git commit/push was performed. `SPLIT_UNVERIFIED` remains active.
