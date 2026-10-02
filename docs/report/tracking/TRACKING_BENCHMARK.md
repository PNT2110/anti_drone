# Tracking-only benchmark

`scripts/benchmark_tracking.py` measures tracker behavior without model
inference or image decoding. It accepts JSON, JSONL/NDJSON, or CSV records.
Each record has `frame_id`, optional `timestamp`, and either a `detections`
array or one `bbox`/`confidence` pair.

Example:

```bash
python scripts/benchmark_tracking.py \
  --input tests/data/tracking_sample.jsonl \
  --drop-every 4 \
  --output runs/tracking-benchmark.json
```

The report runs legacy, motion, and motion-adaptive profiles and records
processed frames, source-frame gaps, IDs created, mean/p50/p95/p99 tracker
latency, and peak RSS delta as reported by the host OS. It reports
`ground_truth_metrics: null` unless identity ground truth is supplied; it does
not invent MOTA/IDF1 values from detections alone.

The sample smoke run on this host completed for all three trackers. It is a
functional and tracking-cost benchmark, not a Pi 5 acceptance result and not
an end-to-end detector FPS measurement.
