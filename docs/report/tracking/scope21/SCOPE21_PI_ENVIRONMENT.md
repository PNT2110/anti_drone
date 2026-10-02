# Scope 21 — Pi environment

The benchmark used a project-local virtualenv at `~/antidrone-scope21/venv`; system Python and OS packages were not modified.

- Python: 3.13.5
- ONNX Runtime: 1.26.0, CPUExecutionProvider
- NCNN: 1.0.20260526
- NumPy: 2.5.3
- OpenCV: 5.0.0
- Threads: 4 for every candidate
- RAM before: 3.95 GiB total, 3.40 GiB available
- RAM after: 3.25 GiB available
- Temperature: temp=51.0'C → temp=73.0'C
- Throttling: throttled=0x0 → throttled=0x0

The ONNX Runtime GPU-discovery warning was non-fatal; all ONNX runs explicitly used `CPUExecutionProvider`.
