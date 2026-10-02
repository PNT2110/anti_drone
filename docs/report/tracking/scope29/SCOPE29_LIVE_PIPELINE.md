# Scope 29 — Live Pipeline

Run-by-command only, headless log-only mode:

`python scope29_pi_live.py --config smoke_config.json --mode smoke`

Capture thread -> bounded latest-frame queue -> frozen NCNN/Scope 28 dual stream -> existing ByteTrack -> target preview -> JSONL state log. No GUI, service, cron, autostart, upload, or cloud path is created.

Per-frame logs include capture monotonic timestamp, source resolution, HIGH/LOW detections, track IDs, target state, stage latencies, capture-to-result age, and actuator-disabled preview.
