# Scope 18 — Training matrix

Fixed order: YOLOv8n-640, YOLOv8n-480, YOLOv11n-640, YOLOv11n-480, YOLO26n-640, YOLO26n-480. Every run uses epochs=100, seed=42, workers=4, device=0, starting batch=16 with fallback 8 then 4 on OOM only, repaired V3 train/val, and a unique directory below `artifacts/experiments/scope18-v3-labelrepair/`.

| Run | Model | Image size | Status | Attempts | Effective batch | Best epoch | best.pt SHA-256 | last.pt SHA-256 |
|---|---:|---:|---|---:|---:|---:|---|---|
| scope18-yolov8n-640 | yolov8n | 640 | COMPLETE | 1 | 16 | 64 | debcef45f0a1667f16c62daf7a8f42d0e5932be498b549b2f985bc72915e9718 | c091d02549067e0f81daad78a3e168714a769cd66bf046cedffde058dee487ca |
| scope18-yolov8n-480 | yolov8n | 480 | COMPLETE | 1 | 16 | 82 | 359ddd23b283cd0eca15927b13b93c6045236f01bcf2bcd574b21f8b16b2ba3e | e5b14fb20182cfce3051ba87bf623356cecf22c1af28e62469b1a24e17c0293c |
| scope18-yolov11n-640 | yolov11n | 640 | COMPLETE | 1 | 16 | 72 | ab2d146424a2c9c0ce053b122463d7d2e796834e9671a60bdeacd4047ca68186 | 2550f80b633b893cb2e130d0a72627911293919e6b8992881685ded4a58188e5 |
| scope18-yolov11n-480 | yolov11n | 480 | COMPLETE | 1 | 16 | 53 | 6f086a2206a466c1037e6aab3ddbbf1afc40b38f7643e9be4f83a85630a81e05 | c8c38e2471a0ed57e7d25c7f1e5bbbab0e071049b901cedc6aec991e898100b5 |
| scope18-yolo26n-640 | yolo26n | 640 | COMPLETE | 1 | 16 | 60 | 3153d0ffdd6b4db7b3fd28fa4026636fe3ffad19acaedbea1c4f35c996fb8bae | 55e5f8c723eb6f99d8e70499bd5f00e7afe562562466927ed116e4879d6684de |
| scope18-yolo26n-480 | yolo26n | 480 | COMPLETE | 1 | 16 | 53 | 1500fb46bbf01910f85a0b75b37e00f275bf0cb725c0829e7c2db293ea6a23d6 | 7e3f88254d58fd2e103068f62c7f9b9105e4c5c34d7f4ebfd6e8048a3b7882d2 |
