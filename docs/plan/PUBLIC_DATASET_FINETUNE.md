# Public indoor/outdoor dataset extension

This extension keeps the detector single-class (`0 = drone`) and adds an
audited indoor source before fine-tuning the existing lightweight checkpoint.

## Sources

- `YOLOv5_drone_detection` / Zenodo record 14878618: indoor RGB/multimodal
  Vicon data, used under the record's CC BY 4.0 terms.
- The existing local `my_dataset` remains user-provided and is pinned to the
  training split.

## Reproducible commands

```bash
python scripts/ingest_public_drone_datasets.py \
  --archive '/run/media/pnt/LINH TINH/anti_drone_data/raw/YOLOv5_drone_detection.zip' \
  --extract /run/media/pnt/HOC/anti_drone_data/raw/vicon_extract \
  --output /run/media/pnt/HOC/anti_drone_data/processed/vicon_indoor

python scripts/merge_yolo_single_class.py \
  --existing /home/pnt/my_dataset \
  --public /run/media/pnt/HOC/anti_drone_data/processed/vicon_indoor \
  --output /run/media/pnt/HOC/anti_drone_data/processed/merged_drone

conda run -n antidrone python scripts/train_public_finetune.py \
  --data /run/media/pnt/HOC/anti_drone_data/processed/merged_drone/data.yaml \
  --weights /home/pnt/drone_web/models/yolo26n.pt \
  --project /run/media/pnt/HOC/anti_drone_data/runs \
  --epochs 80 --imgsz 640 --batch 8
```

The scripts emit `manifest.json`, `license_ledger.json`, checksums, and a
separate run directory so the currently deployed model is not overwritten.
