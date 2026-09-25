# Scope 22 — INT8 export report

Status: **ARTIFACTS CREATED; NONE READY FOR DEPLOYMENT**.

| Candidate | Input size | Export status | Param SHA-256 | Bin SHA-256 | Total MiB | INT8 graph markers |
|---|---:|---|---|---|---:|---:|
| `scope18-yolov8n-480` | 480/640 | INT8_RUNTIME_CANDIDATE | cce164b70dd911f1cd325501365ac0119f8d2f779e28e8b1ee2fc03c0fdba314 | 547b5de1ebf39fab4490809a343bcd4f558b11c02d8ea0c45a8cf5bb984bf108 | 2.971 | 64 |
| `scope18-yolov8n-640` | 480/640 | INT8_RUNTIME_CANDIDATE | c19bc6183d53d640994e3bfce968f29b65784ecebd5c29daab883f4c2ed397ec | ecd36842e6e57903246213b87f918cf75c5de6394c37a606bf5e8d6518f18a9a | 3.013 | 64 |
| `scope18-yolov11n-480` | 480/640 | INT8_RUNTIME_CANDIDATE | 27783fb3034e5bdab2d89312bdddff4b1d5b31ed8c5aa2e7312d83386eb6b7c6 | 499f85d70de7f7017cde07af30dd9287dd55af9e96bc7b59a09b28ca0729bc13 | 2.589 | 88 |

`ncnn2int8` returned success for all three, but host diagnostic parity is the required next gate. These artifacts are Scope 22-only and do not overwrite Scope 19/20 exports.
