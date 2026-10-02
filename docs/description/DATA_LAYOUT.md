# Anti-drone training data layout

The remote training data is kept on the separate ext4 volume mounted at
`/mnt/home_big`.

```text
/mnt/home_big/pnt/anti_drone_data/
├── raw/
│   └── seraphim/                  # downloaded archives; preserve provenance
├── processed/
│   ├── vicon_indoor_mask_yolo/    # AirSim RGB frames + mask-derived YOLO boxes
│   └── seraphim_yolo/             # outdoor/general drone YOLO data
├── merged_fp_indoor_outdoor_v1/   # immutable train/val/test materialization
└── training_runs/
    └── fpv-indoor-outdoor-v1/     # Ultralytics run and checkpoints
```

The current immutable materialization contains 94,232 image/label pairs:

- `images/train`: 52,241
- `images/val`: 21,991
- `images/test`: 20,000

The merged source counts are 2,138 existing project images, 16,961 Vicon
indoor images, and 75,133 Seraphim outdoor/general drone images. Every split
currently has one label file per image; `manifest.json` records source and
split provenance.

For local inspection, the same verified tree is available at
`data/data_train/` in this repository. Its `data.yaml` uses
the local absolute path.

The Purdue multi-target UAV source is kept separately under
`raw/purdue_uav/` on the server until its video archive finishes downloading;
`scripts/ingest_purdue_uav.py` converts its refined MOT annotations to
single-class YOLO while splitting by clip.

The user video is intentionally excluded from production training until its
labels are manually corrected. `manifest.json` and `license_ledger.json` in
the processed and merged roots are the source/provenance records.

Sources:

- Vicon drone-swarm archive: https://zenodo.org/records/14878618
- Seraphim drone dataset: https://huggingface.co/datasets/lgrzybowski/seraphim-drone-detection-dataset
