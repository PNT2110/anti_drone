# Scope 05 — Halmstad Source Provenance Report

## Status

`SPLIT_UNVERIFIED`

There is no confirmed exact source overlap, but the available provenance is not
sufficient to claim `CONFIRMED SOURCE-DISJOINT`.

## Checkpoint trace

| Item | Evidence |
|---|---|
| Release model | `artifacts/deploy/yolov8n/onnx/best.onnx` |
| Training checkpoint | `artifacts/experiments/drone-single-class/yolov8n/baseline-640-s42-drop01-2/weights/best.pt` |
| Checkpoint SHA-256 | `662fbc1c066041345970f4211a6ceb9209907a331fd1724c0b2be7e53a4beec1` |
| Training dataset | `data/processed/drone-single-class/data.yaml` |
| Dataset manifest SHA-256 | `3626696d97126c0e8da925c4bf3d282168c8ed3615361f3f536ec614eb94317d` |
| Release-record manifest SHA-256 | same; exact match |
| Training seed | 42 |
| Training run | `baseline-640-s42-drop01-2`, 100 epochs, 640 input |
| Provenance source | `anti_drone_provenance.json` and release metadata |

The checkpoint is reproducibly tied to the current processed manifest. That
manifest contains 34,398 `base` and 2,334 `my_dataset` samples, but each row
has image/group provenance rather than an archive-member/video identity key.

## Halmstad comparison

| Check | Result |
|---|---:|
| `V_DRONE_001` exact name in processed manifest | 0 hits |
| Exact source-frame/hash match established | No |
| Halmstad archive member key in training manifest | Not present |
| Halmstad video SHA-256 | `9db5a800377c01db8369dfba808d400ca52cd393e0a32850e1d20a4861eaecbe` |
| Halmstad sidecar SHA-256 | `39598c0beded8754d5193f57306897dd9302a309c9e391c37ada23eb94646399` |
| pHash screening | 8 video frames; nearest distances 9–14 |

The pHash nearest images are generic visually similar training images and are
not accepted as overlap evidence. Perceptual similarity alone cannot identify
the same source video. Conversely, absence of the literal filename cannot
prove source disjointness because the processed manifest does not preserve the
Halmstad archive member relationship.

## Conclusion

Keep `SPLIT_UNVERIFIED`. Do not label Halmstad as an independent validation
sequence until archive-level provenance or an equivalent source mapping is
established.
