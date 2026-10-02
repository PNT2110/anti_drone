# Repository layout

The project keeps the existing functional directories and separates source code,
data, runtime state, artifacts, deployment, and documentation:

```text
anti_drone/
├── configs/                         # tracked dataset, model, tracker, and train configs
│   ├── datasets/
│   ├── models/
│   ├── trackers/
│   └── training/
├── data/                            # local/raw/generated data; not committed
│   ├── data_train/                  # canonical image/label dataset
│   ├── import_data_rar/             # source archives
│   ├── incoming/                    # incoming data staging
│   └── processed/                   # validated source conversions
├── .runtime/                        # machine-local run state; not committed
│   ├── datasets/
│   ├── training/
│   └── exports/
├── artifacts/                       # checkpoints, experiments, reports, deploy bundles
│   ├── models/
│   ├── experiments/
│   ├── deploy/
│   └── reports/
├── docs/                            # English filenames and documentation
│   ├── description/
│   ├── report/
│   └── plan/
├── scripts/                         # dataset, training, audit, export, and deploy tools
├── src/anti_drone/                  # Pi 5/runtime source code
├── web/                             # public web application; preserve separately
├── tests/
└── README.md
```

`web/` and the Pi 5 source/deployment assets are preserved when cleaning old
experiments or dataset staging files. New plans and reports belong in
`docs/plan/` and `docs/report/`.

