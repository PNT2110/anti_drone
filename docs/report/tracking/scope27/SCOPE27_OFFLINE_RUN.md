# Scope 27 — Offline run

Source: Halmstad `V_DRONE_001.mp4`, diagnostic-only, 301 sequential frames at 30 FPS and 640×512. No frame skipping or silent dropping occurred. `frames_expected = frames_processed = 301`.

The source video was copied to a dedicated Pi workspace and processed sequentially. V3 TEST was not used for integration or tuning. Per-frame target state is in [`target_state.jsonl`](../../../.runtime/scope27/target_state.jsonl).
