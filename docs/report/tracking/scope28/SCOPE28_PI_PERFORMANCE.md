# Scope 28 — Pi 5 Performance

Hardware: Raspberry Pi 5 Model B Rev 1.0, aarch64, 4 GiB-class RAM, NCNN FP32, 4 threads. The run used the offline Halmstad file; these are not webcam FPS claims.

| Metric | Value |
|---|---|
| decode_read_ms | mean=0.6820 ms; p50=0.6841 ms; p95=0.7184 ms |
| preprocess_ms | mean=1.8070 ms; p50=1.8057 ms; p95=1.8824 ms |
| inference_ms | mean=36.1529 ms; p50=36.1339 ms; p95=36.4400 ms |
| candidate_decode_ms | mean=4.7001 ms; p50=4.6937 ms; p95=4.8019 ms |
| nms_ms | mean=0.0178 ms; p50=0.0213 ms; p95=0.0245 ms |
| stream_split_ms | mean=0.0035 ms; p50=0.0034 ms; p95=0.0039 ms |
| postprocess_ms | mean=4.7222 ms; p50=4.7179 ms; p95=4.8294 ms |
| tracker_update_ms | mean=0.4864 ms; p50=0.5314 ms; p95=0.7024 ms |
| target_selection_ms | mean=0.0054 ms; p50=0.0056 ms; p95=0.0063 ms |
| total_pipeline_ms | mean=43.9801 ms; p50=43.9194 ms; p95=44.3944 ms |
| Effective sequential FPS | 22.7375 |
| Scope 27 total baseline | 44.5422 ms mean; 22.4506 FPS |
| Temperature | temp=48.8'C -> temp=52.1'C |
| Throttling | throttled=0x0 -> throttled=0x0 |
| Available RAM | 3741237248 -> 3667050496 bytes |

The measured total pipeline remained close to Scope 27. Candidate decode and one-NMS/split stages are separated in the evidence. No frame skipping was used.
