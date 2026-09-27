# Scope 28 — Final Report

Final status: `BYTETRACK_TWO_STAGE_INPUT_CONTRACT_RESTORED`

| Metric | Value |
|---|---|
| Scope 27 discarded 0.10–<0.25 before ByteTrack? | YES |
| Freeze manifest unchanged | e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964 |
| Scope 26 headline unchanged | 7c5c6c6a724f0036e936ff2dd84917e2f78a44cf091d5ca8b64d1480e8bb3e83 |
| Candidate hashes unchanged | param=8d1a2d62f65c5a44f138dd2a2da43fa87246ecb6948f9a020b7cc86a46d095c5; bin=23092b6c934f9863efd68ab5e5343e8cc84e7acfb97db8c68b963ba6ee28cfd7 |
| High stream equivalence | 8/8 and 301/301 PASS |
| Frames with low detections | 15 |
| Low-only frames | 15 |
| Low observations inferred in association | 13 |
| Track IDs | [1, 2, 3, 4, 5] |
| ID changes | 2 |
| Lost/reacquisition | 11/10 |
| Prediction-only/no-target | 31/53 |
| Total latency mean/p95 | 43.9801/44.3944 ms |
| Effective FPS | 22.7375 |
| Temperature/throttling | temp=48.8'C -> temp=52.1'C; throttled=0x0 -> throttled=0x0 |
| Actuator writes | 0/0/0 GPIO/PWM/serial |
| V3 TEST tuning | No |
| Webcam/physical actuation | No / No |

Scope 28 restored the intended ByteTrack two-stage input contract in an external adapter while retaining the frozen public detector semantics. The adapter performs one inference and one NMS per frame, passes high and low observations with original confidence and source-frame coordinates, and leaves `bytetrack_motion_adaptive` unchanged. The 301-frame Halmstad run completed on the verified Pi 5. This remains a diagnostic dry-run, not an independent test or a generalization claim.

Required stop condition: do not start Scope 29 automatically.
