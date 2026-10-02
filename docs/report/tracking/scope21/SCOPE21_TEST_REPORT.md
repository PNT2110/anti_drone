# Scope 21 — Test report

Host checks:

- `PYTHONPATH=. python -m pytest -q` — **PASS**, 106 passed, 1 skipped.
- `python -m compileall -q scripts src tests` — **PASS**.
- `git diff --check` — **PASS**.
- `python scripts/scope20_parity.py --phase audit` — **PASS**, six checkpoints and 12 Scope 19 exports match.

Pi checks:

- Pi identity: PASS (`Raspberry Pi 5 Model B Rev 1.0`, `aarch64`).
- Artifact transfer verification: PASS for all 10 candidates.
- Runtime parity: PASS for all 10 candidates on all 8 fixed images.
- TEST access: false.
- YOLO26 NCNN candidate inclusion: false.
- Production freeze: false.

An initial diagnostic run exposed and discarded a harness-only NCNN preprocessing error (float tensor passed to an API requiring uint8 before normalization). The corrected harness was transferred and the complete 10-candidate protocol was rerun; only the corrected run is reported.
