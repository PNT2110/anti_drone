# Scope 22 — NCNN INT8 toolchain

Status: **TOOLCHAIN_SUPPORTED; DEPLOYMENT_PATH_BLOCKED_BY_DIAGNOSTIC_PARITY**.

The installed Python wheel was NCNN `1.0.20260526`. Its exposed `quantize_to_int8` API is tensor-level only; the model PTQ workflow required the official command-line tools. An isolated host build from NCNN tag `20260526` / commit `e54f7b1f88434e1d844ea0551b880a1cfb079ce1` produced `ncnn2table`, `ncnn2int8`, and `ncnnoptimize` without changing the project Conda environment or Pi Scope 21 venv.

Workflow used for each candidate:

1. `ncnn2table <param> <bin> calibration_images.txt <table> mean=[0,0,0] norm=[0.003921568627,...] shape=[size,size,3] pixel=RGB thread=4 method=kl`
2. `ncnn2int8 <param> <bin> <int8.param> <int8.bin> <table>`

The exports were PNNX-derived NCNN artifacts, so `ncnnoptimize` was not inserted before `ncnn2table`; this follows the official NCNN PTQ workflow for PNNX output. The logs, commands, tables, and hashes are under `.runtime/scope22/work/`.

All three `ncnn2table` and `ncnn2int8` commands returned 0. The resulting param graphs contain NCNN int8 scale-term markers (`8=2`) and the binary sizes shrink materially. These are real INT8 artifacts, but they are not READY because host behavior degraded.
