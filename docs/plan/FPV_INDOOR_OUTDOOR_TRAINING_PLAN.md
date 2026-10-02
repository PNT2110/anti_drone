# FPV indoor/outdoor training plan

## Scope

- Keep the current project layout unchanged.
- Use `data/data_train` as the canonical local dataset directory.
- Keep image/label pairs only; exclude unlabelled or mismatched samples.
- Preserve the web application and Pi 5 deployment assets.
- Train on the SSH GPU host, then validate, export, and deploy the best checkpoint.

## Training safeguards

- Resume from the existing checkpoint when possible instead of restarting.
- Keep train, validation, and test splits separate.
- Select `best.pt` by validation fitness and evaluate the locked test split only after training.
- Preserve provenance, manifests, and conversion reports under `docs/report/`.

## Export and deployment sequence

1. Finish training and record final validation/test metrics.
2. Export the selected checkpoint to ONNX, NCNN, and TFLite where the runtime supports it.
3. Run parity/smoke checks for each export.
4. Copy the verified ONNX model to the web model directory and activate it through the model switch API.
5. Keep Pi 5 assets unchanged until the new model passes the deployment checks.
