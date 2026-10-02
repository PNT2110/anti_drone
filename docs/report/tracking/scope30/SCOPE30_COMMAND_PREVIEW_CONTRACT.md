# Scope 30 — Command Preview Contract

Frame center is `(width/2, height/2)`. Pixel error is `target_center - frame_center`. Normalized error is `2 * pixel_error / frame_dimension`, clamped to `[-1, +1]` only in the software preview layer. Raw normalized desired pan/tilt equals the normalized error for TRACKING and HOLD_PREVIEW states.

Envelope is normalized-only: neutral `0.0`, minimum `-1.0`, maximum `+1.0`, maximum change `0.25` per frame. The preview reports raw, bounded, and rate-limited values. No physical pulse width, angle, PWM duty, GPIO, serial value, or hardware direction was inferred.
