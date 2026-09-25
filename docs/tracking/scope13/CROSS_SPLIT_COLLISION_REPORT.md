# Scope 13 — Cross-Split Collision Report

## Sequence level

**Confirmed cross-split source-sequence collisions: 0.** Every one of the 318 V2 groups maps to one unique Anti-UAV300 source sequence directory, and each mapped sequence appears in exactly one V2 split. Visible and infrared rows for each sequence remain together.

## Session level

**Confirmed cross-split session collisions: 0; session-level relationship UNKNOWN for 47 prefixes.** The 47 cross-split prefixes are date/time candidates with multiple distinct archive sequence directories. No archive metadata defines a shared session ID, so they cannot be counted as confirmed collisions or confirmed independent sessions.

This distinction is intentional:

- sequence-level source mapping is confirmed;
- session-level source independence is not proven;
- no V2 split was edited;
- no quarantine sample was promoted;
- no V3 was created.

If Research & Design requires session-disjoint rather than sequence-disjoint data, the next step is to obtain/define authoritative session metadata. The current archive evidence does not justify grouping all equal date/time prefixes automatically.
