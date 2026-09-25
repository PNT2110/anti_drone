# Scope 08 — Alert Event Audit

## Semantics checked

The audit distinguishes detector presence, tracker observation,
prediction-only state, GT IoU match, alert creation, and source frame. An
observed tracker box is not required to have GT IoU `>=0.50` to count as an
observation. A prediction-only track is never passed as a new observation to
the alert history.

The unchanged alert policy is: 3 observations, 2 high-confidence observations,
0.60-second confirmation window, 2.0-second cooldown, and high-confidence
threshold 0.25.

## Legacy frame 153

The event is valid and is not prediction-only:

- event/creation/source frame: 153;
- timestamp: `5.066666667`;
- track ID: 2;
- `observed=true`, `predicted=false`, `matched_this_frame=true`;
- detector confidence: `0.2874256`;
- GT IoU: `0.409593`, therefore no GT match at the fixed 0.50 diagnostic rule;
- observation history: source frames 151, 152, 153;
- confidence history: `0.2893`, `0.2797`, `0.2874`, with all three above 0.25;
- result: 3 observations and at least 2 high-confidence observations, so the
  alert policy was satisfied.

The apparent contradiction in Scope 07 is semantic: “no GT match” does not
mean “prediction-only.” The tracker was observing real cached detections.

## Motion frame 156

The event is also valid and is not prediction-only:

- event/creation/source frame: 156;
- timestamp: `5.166666667`;
- track ID: 4;
- `observed=true`, `predicted=false`, `matched_this_frame=true`;
- detector confidence: `0.1401639`;
- GT IoU: `0.401781`, therefore no GT match at IoU 0.50;
- observation history: source frames 154, 155, 156;
- confidence history: `0.3902`, `0.4717`, `0.1402`; the first two satisfy the
  high-confidence requirement;
- result: 3 observations and 2 high-confidence observations, so the alert
  policy was satisfied.

There was no delayed event frame in either case: event frame, source frame,
and timestamp refer to the same replay record.

## Invariants

Across all three profiles:

- prediction-only alert events: `0`;
- duplicate source-frame alerts: `0`;
- all alert events include event ID, creation/source frame, timestamp, track
  ID, bbox, confidence, and the preceding history in the Scope 08 trace;
- the regression tests explicitly cover prediction-only and duplicate-source
  suppression.

No alert threshold or cooldown was changed. No alert implementation bug was
found in this audit.
