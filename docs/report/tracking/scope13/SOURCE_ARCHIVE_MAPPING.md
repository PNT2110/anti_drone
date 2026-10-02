# Scope 13 — Source Archive Mapping

## Result

All 30,227 assigned rows map to `Anti-UAV300.tar` by a deterministic, reproducible archive schema:

```text
V1 RGBT_<source_split>_<date>_<time>_<stream>_<sequence>_<modality>_<frame>.jpg
→ Anti-UAV300/data/Anti-UAV300/<source_split>/<date>_<time>_<stream>_<sequence>/<modality>.mp4
→ matching <modality>.json[frame]
```

The mapping has exact archive directory/member existence, exact modality, and a valid zero-based frame index into the matching JSON `exist`/`gt_rect` arrays. It resolves 318/318 groups and 30,227/30,227 samples. The V2 split is a separate field from the original source split encoded in the filename; it is not used to construct the archive path.

| Evidence | Count |
|---|---:|
| Archive-member/source-frame mappings | 30,227 |
| Groups mapped to unique archive sequence directories | 318 |
| Visible samples | 14,713 |
| Infrared samples | 15,514 |
| Missing archive video/annotation members | 0 |
| Frame indices out of JSON range | 0 |

## Representative content corroboration

Six preselected representatives were decoded: visible and infrared members from three deterministic groups (first, middle, and last sorted group). The command was:

```text
ffmpeg -hide_banner -loglevel error -i <member.mp4> -vf select='eq(n,<zero_based_frame>)' -frames:v 1 -q:v 2 <representative.jpg>
```

No resize or crop was applied. All six had matching dimensions and passed the declared comparison rule: mean absolute pixel difference ≤10 and max channel difference ≤64 after independent JPEG encoding. Observed mean differences were approximately 0.43–1.40 and max differences 13–17. This corroborates the mapping; it is not byte equality because V1 JPEG and decoded/re-encoded video frames can differ.

The six representative commands, source members, frame indices, probe dimensions/FPS, and comparison results are recorded in `.runtime/scope13/rgbt_provenance_summary.json`.

Evidence rows: `.runtime/scope13/rgbt_archive_mapping.csv`. Group evidence: `.runtime/scope13/group_archive_evidence.json`.

## Limits

The repository's `prepare_dataset.py` verifies the V1 grouping transform but does not contain the original archive extraction command. Therefore the mapping is confirmed by the source naming contract, exact archive members, JSON frame bounds, and representative decode—not by a byte-level match for every compressed video frame. This is sufficient to identify the source sequence/member/frame, but not sufficient to infer a higher-level session identity.
