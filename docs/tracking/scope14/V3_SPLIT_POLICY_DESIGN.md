# Scope 14 — V3 Split Policy Design

## Option A — Current V2

Keep the 318 mapped source sequence directories atomic. This is the accepted V2 baseline and is not rebuilt. It has zero source-sequence overlap across V2 splits, but 47 date/time prefixes cross V2 splits and the session relationship for those prefixes is UNKNOWN.

## Option B — Conservative prefix-atomic V3

Use the 63 date/time prefixes as candidate groups. This is a risk-control candidate key, not a claim that equal timestamps mean one recording session. A conservative holdout policy keeps each candidate prefix in the original Anti-UAV300 partition it came from:

- original `train` prefix → candidate V3 train;
- original `val` prefix → candidate V3 val;
- original `test` prefix → candidate V3 test.

This policy yields 12,142 train, 8,237 val, and 9,848 test samples. It preserves all original source boundaries, source sequences, visible/infrared pairs, and candidate prefixes, but deviates substantially from 70/20/10. The deviation is preferable to splitting an official source partition merely to improve ratios.

A separate deterministic seed-42 target-ratio preview was computed for comparison only. It would assign 43 candidate prefixes / 18,030 samples across the protected original boundary and is therefore marked `BLOCKED_BY_ORIGINAL_HOLDOUT_BOUNDARY`. It is not a valid production assignment.

Neither option proves session-disjointness. Prefixes are only candidate groups until authoritative session metadata exists. No V3 was selected, materialized, or given a production `data.yaml`.
