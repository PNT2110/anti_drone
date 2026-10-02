# Scope 28 — Contract Diagnosis

Result: `CONTRACT_GAP_CONFIDENCE_FLOOR`

Scope 27 **did discard** `0.10 <= confidence < 0.25` before `ByteTrack.update`. Evidence was read directly from `scripts/scope27_pi_dryrun.py`, `scripts/scope21_pi_runner.py`, and `src/anti_drone/tracking/bytetrack.py`: Scope 27 called the decoder with `CONF = 0.25`; that decoder filtered candidates before returning; the tracker’s `track_low_thresh=0.10` therefore had no low observations to receive.

This was a real contract gap, so the adapter was implemented. The tracker implementation and its profile/config were not changed.
