# Data directory cleanup — 2026-09-30

The top-level `data/` directory now contains only the two active areas:

```text
data/
├── data_train/       # canonical 110,469-image YOLO dataset
└── import_data_rar/  # source archives and extracted/legacy imported data
    ├── extracted/
    └── legacy_local/
```

The source archives in `data/import_data_rar/` were preserved. Existing extracted
or legacy data was moved under `legacy_local/`; the validated DUT/UAV-CB extraction
was moved under `extracted/`. `data_train/` was not moved or deleted.
