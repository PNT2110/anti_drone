# Scope 16 — Training Matrix

Sáu run bắt buộc đã được hạch toán trong `.runtime/scope16/training_matrix.json`. Tất cả đều `NOT_STARTED_LABEL_PREFLIGHT`; không có run nào tạo checkpoint, log epoch hoặc validation metrics.

| Model | imgsz | Config | Trạng thái |
|---|---:|---|---|
| YOLOv8n | 640 | `configs/training/scope15/yolov8n_640.json` | NOT_STARTED_LABEL_PREFLIGHT |
| YOLOv8n | 480 | `configs/training/scope15/yolov8n_480.json` | NOT_STARTED_LABEL_PREFLIGHT |
| YOLOv11n | 640 | `configs/training/scope15/yolov11n_640.json` | NOT_STARTED_LABEL_PREFLIGHT |
| YOLOv11n | 480 | `configs/training/scope15/yolov11n_480.json` | NOT_STARTED_LABEL_PREFLIGHT |
| YOLOv26n | 640 | `configs/training/scope15/yolo26n_640.json` | NOT_STARTED_LABEL_PREFLIGHT |
| YOLOv26n | 480 | `configs/training/scope15/yolo26n_480.json` | NOT_STARTED_LABEL_PREFLIGHT |

Không chạy song song, không thử batch OOM và không resume vì chưa có run nào bắt đầu. Output root dành riêng là `artifacts/experiments/scope16-v3/`, hiện chưa được tạo.
