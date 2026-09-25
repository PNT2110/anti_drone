# Scope 26 — Test report

Primary NCNN TEST evaluation completed with protocol integrity PASS.

- Freeze manifest verified before opening TEST: `e4b2521b02d0a2b32f123cf33c5d5c64fc136fcc65d4d6f400050539d6264964`.
- First TEST event: `2026-09-25T19:12:40.602499+00:00`.
- Expected/processed/skipped: `9848 / 9848 / 0`.
- Primary backend: NCNN FP32 on Raspberry Pi 5; runtime `1.0.20260526`.
- No PyTorch primary evaluation, model switch, threshold sweep, or post-open contract change.
- Pi temperature: `temp=41.1'C → temp=59.3'C`; throttling `throttled=0x0 → throttled=0x0`.

Required checks:

```text
python -m pytest -q
python -m compileall -q scripts src tests
git diff --check
```

Results: `126 passed, 1 skipped`; `compileall` PASS; `git diff --check` PASS.

Machine-readable metric audit: [`metric_audit.json`](../../../.runtime/scope26/metric_audit.json).
