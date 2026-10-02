# Scope 10 — Source Archive Inventory

Inventory status: **PASS**. Six local archives were inspected by tar listing; none was expanded wholesale. Archive hashes below are the hashes recorded by the existing manifest/audit and were cross-checked against current archive paths and sizes. They were not recomputed again in Scope 10 for the multi-gigabyte files.

| Archive | Size | Members / files | Video members | Annotation-like members | Apparent sequence IDs | Modalities / format evidence |
|---|---:|---:|---:|---:|---:|---|
| `Anti-UAV300.tar` | 16,778,137,600 B | 2,110 / 1,681 | 836 MP4 | 839 JSON | 318 date/camera groups | visible + infrared/RGB; MP4+JSON |
| `DUT-Anti-UAV.tar` | 10,277,939,200 B | 44,889 / 44,849 | 0 | 10,041 XML/TXT | 20 `videoNN` groups | image detection and tracking GT; JPG+XML/TXT |
| `Drone-vs-Bird.tar` | 4,136,960 B | 128 / 107 | 0 | 77 TXT | no reliable temporal IDs in listing | image/annotation repository; JPG+TXT |
| `Halmstad-Drone.tar` | 665,937,920 B | 1,445 / 1,423 | 652 MP4 | 651 MAT | 650 visible/IR members | visible + IR; MP4+MAT |
| `UAV-CB.tar` | 6,088,161,280 B | 13,590 / 13,573 | 0 | 6,786 JSON | no reliable sequence IDs from names | visible + thermal; JPG+JSON |
| `my_dataset.tar.xz` | 616,009,768 B | 4,664 / 4,663 | 0 | 2,328 TXT | static image set | JPG+TXT |

Recorded archive SHA-256 values:

```text
c8af3934b7b84c21f1ecfda4723c11b186a6c7182c1ece2b629ebc2035fa6e2f  Anti-UAV300.tar
5e7c17b051120d731fe7ac289db1328012daf41f4d8ff349cfe366dc7e926e34  DUT-Anti-UAV.tar
c35c5fe8d7fdae051b654a92eff3f34fd256bf54b91e54e36aafa0d2d3948edc  Drone-vs-Bird.tar
f525a5448b4ed0e6e01ad67efcd22057d8e65e203124f32b5c97101d1c292dff  Halmstad-Drone.tar
21f893587e543ade6406225c0a87f845ce67328d4448c42ef84b8fcbc42460e4  UAV-CB.tar
43a3f2a25a175b5e043b789309a89fbf33493f2815bec5ac4effb29296f47caf  my_dataset.tar.xz
```

Halmstad member inspection confirmed paired visible video/MAT members for the selected `V_DRONE_046`, `V_DRONE_048` and `V_DRONE_045` sequences. The current repository contains `data/tracking_eval/sequence_004/source/V_DRONE_045.mp4` and `V_DRONE_045_LABELS.mat`; it does not contain `V_DRONE_051` under `data/tracking_eval/`. Only the six current selected members were extracted. Machine-readable inventory: `.runtime/scope10/source_archive_inventory.json`.
