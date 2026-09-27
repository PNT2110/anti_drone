# Scope 30 — Loss-of-Target Safety

The preview state machine is deterministic: observed target → `TRACKING`; predicted target → `HOLD_PREVIEW`; target absent → `RETURN_NEUTRAL_PREVIEW` and then `NO_TARGET`; camera failure → `SAFE_NO_TARGET`. After target invalidation, the preview cannot retain a non-neutral command indefinitely. Physical output remains disabled.

## Scope 30R2 / Attempt 3

No live target transition was attempted after the alignment gate failed. Software state-machine tests remain valid.

## Scope 30R2 / Attempt 4 — live loss evidence

Observed command-preview states: `['HOLD_PREVIEW', 'NO_TARGET', 'RETURN_NEUTRAL_PREVIEW', 'TRACKING']`. Natural transitions included `TRACKING → HOLD_PREVIEW → RETURN_NEUTRAL_PREVIEW → NO_TARGET`; final no-target output was neutral. Software camera-failure guard remains `SAFE_NO_TARGET` with prior `CAMERA_OPEN_FAILED` evidence.
