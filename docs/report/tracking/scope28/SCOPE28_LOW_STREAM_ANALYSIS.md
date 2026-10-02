# Scope 28 — LOW Stream Analysis

| Metric | Value |
|---|---|
| Frames with any low detection | 15 |
| Low-only frames | 15 |
| Low boxes retained | 15 |
| Frames with inferred LOW association | 13 |
| Tracker floor | 0.10 |
| Frozen public threshold | 0.25 |

Low observations were present on the Halmstad run and 13 were inferred to participate in association. The inference is based on IoU equality of the observed tracker box with the frame’s low-stream box; the existing ByteTrack code was not instrumented or modified. Low observations were never promoted to high confidence and did not create new tracks by themselves.

The exact frame/box evidence is in `.runtime/scope28/low_stream_analysis.json` and `artifacts/integration/scope28/low_stream_analysis.json`.
