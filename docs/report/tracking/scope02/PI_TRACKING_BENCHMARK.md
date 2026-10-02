# Scope 02 tracking benchmark

## Pi status

The requested Pi tracking benchmark is `BLOCKED — PI HARDWARE ACCESS`. No
sustained benchmark was run, and no x86 result is presented as a Pi result.

## Host reference benchmark

For preparation, the same eight-record detector caches were passed through all
three profiles. This measures tracking-only latency; inference and image
decoding are excluded.

### ONNX cache

| Profile | Frames | Mean ms | P50 ms | P95 ms | P99 ms | Peak RSS delta KB |
|---|---:|---:|---:|---:|---:|---:|
| legacy | 8 | 0.0180 | 0.0055 | 0.0526 | 0.0571 | 0 |
| motion | 8 | 0.1111 | 0.0559 | 0.2533 | 0.2638 | 1016 |
| adaptive | 8 | 0.0737 | 0.0400 | 0.1948 | 0.2058 | 0 |

### NCNN cache

| Profile | Frames | Mean ms | P50 ms | P95 ms | P99 ms | Peak RSS delta KB |
|---|---:|---:|---:|---:|---:|---:|
| legacy | 8 | 0.0165 | 0.0051 | 0.0472 | 0.0517 | 0 |
| motion | 8 | 0.1126 | 0.0563 | 0.2505 | 0.2617 | 1136 |
| adaptive | 8 | 0.0776 | 0.0396 | 0.2205 | 0.2490 | 0 |

The machine-readable reports are:

```text
.runtime/scope02/benchmark/tracking_profiles.json
.runtime/scope02/benchmark/tracking_profiles_ncnn.json
```

These short host smoke runs have one sequence and eight frames. RSS is a
process-level peak delta and is noisy. No sustained 1,800-second run was
performed, as explicitly prohibited by Scope 02. CPU utilization and
temperature were not measured.

No HOTA, IDF1, IDSW, fragmentation, or ID-retention conclusion is made: the
cache has no identity ground truth.
