# Fresh FPV Training Status — 2026-09-30

## Dataset

- Canonical dataset: `data/data_train`
- Images: 110,469
- Labels: 110,469
- Missing labels: 0
- Orphan labels: 0
- Splits: train 63,028; val 25,781; test 21,660
- Local raw size: approximately 17.1 GB

## Training matrix

Six independent fresh runs are configured:

- YOLOv8n at 480 and 640 pixels
- YOLO11n at 480 and 640 pixels
- YOLO26n at 480 and 640 pixels

The runs use official base weights as the starting point, but do not resume any previous project checkpoint. They use a fixed dataset split, seed 42, deterministic execution, stochastic augmentation, weight decay, label smoothing, cosine learning-rate scheduling, and early stopping. The server runner is `train_matrix_fresh.py`; its local mirror is `scripts/train_matrix_fresh.py`.

## Final training and deployment state

All six fresh runs completed on the server. The selected checkpoint is `yolo26_img640` (`best.pt`), chosen using validation mAP50-95; it is not selected from the test set. The locked test metrics are retained below as a final evaluation, not as a model-selection signal.

| Run | Validation mAP50-95 | Test mAP50-95 |
| --- | ---: | ---: |
| YOLOv8n 480 | 0.67912 | 0.60058 |
| YOLOv8n 640 | 0.70372 | 0.60794 |
| YOLO11n 480 | 0.68217 | 0.60461 |
| YOLO11n 640 | 0.70658 | 0.61203 |
| YOLO26n 480 | 0.68579 | 0.60605 |
| YOLO26n 640 | **0.70910** | **0.61460** |

Across the matrix, test mAP50-95 is about 0.09 lower than validation. That consistent gap warrants a follow-up audit for scene/source distribution shift and split leakage/near-duplicates before interpreting the validation score as expected field performance; it is not evidence by itself that a single neuron or one specific training example dominated learning.

The result artifacts are on the server under `/mnt/home_big/pnt/anti_drone_data/training_runs/fresh_matrix/` and `/mnt/home_big/pnt/anti_drone_data/deployment/`. The selected model has PT, ONNX, NCNN, and TFLite/LiteRT exports. The TFLite export initially failed because `torchao 0.18.0` was incompatible with the server's `torch 2.8.0`; replacing it with `torchao 0.13.0` resolved the import failure and the 640px TFLite export completed successfully. The deployment manifest was updated to record the successful export.

The ONNX, PT, and TFLite files are also in `/home/pnt/drone_web/models/`. The web app was restarted with its virtualenv Python so that it rescanned the models. Verification at `GET /api/models` returned `fresh_yolo26_img640_best.onnx` as active. The service is listening on port 8000. Training and post-processing PIDs `74400` and `80972` are no longer running.

The local data root remains normalized to the two intentional areas: `data/data_train` (canonical training dataset) and `data/import_data_rar` (source archives/legacy imports). The local dataset has 110,469 image/label pairs and no missing or orphan labels in the audit. No further data move is needed while the current manifest and split counts remain valid.

## Local model pull and public web refresh — 2026-10-01

The six `best.pt` checkpoints, each run's `results.csv` and `args.yaml`, the selected ONNX/TFLite/NCNN exports, and the deployment manifests were packaged from the server into `artifacts/models/fresh_matrix_20261001/`. The 54 MB transfer archive SHA-256 was verified as `5d10b73c54225bd437d654460475459a4fdc52a07686863f1c2d1792a66af770`; extracted contents occupy about 120 MB. The six checkpoints were also copied into local `web/models/` using discoverable drone/resolution filenames, with `fresh_yolo26_img640_best.onnx` set as the local default.

The same six PT checkpoints were installed into `/home/pnt/drone_web/models/` and the server web process was restarted. The public Cloudflare tunnel returned HTTP 200 from `/api/models`, listed all six new checkpoints and the fresh ONNX/PT artifacts, and reported `fresh_yolo26_img640_best.onnx` as active. The public URL observed in the tunnel log is `https://vernon-scheme-licensing-chief.trycloudflare.com` (Quick Tunnel URL; not a stable custom domain).
