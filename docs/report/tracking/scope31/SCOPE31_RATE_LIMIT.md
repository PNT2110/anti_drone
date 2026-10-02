# Scope 31 — Physical Rate Limit

No physical servo rate limit was established. Scope 30's normalized preview
limit `0.25/frame` is not converted into a physical pulse slew rate. PAN
returned `NO_RESPONSE` on its first bounded center command, so no further
motion was attempted. A future resumed commissioning run must derive
`us/update` or `us/s` only after response and safe behavior are observed.
