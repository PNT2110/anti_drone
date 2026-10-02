"""
web/backend/config.py
System configuration, directory path resolution, model catalog, and Vietnamese localization settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# ==============================================================================
# 1. System Paths & Directory Structure (Robust Anchor Resolution)
# ==============================================================================
CURRENT_FILE_DIR: Path = Path(__file__).resolve().parent

# Check if located directly within web/backend
if CURRENT_FILE_DIR.name == "backend" and CURRENT_FILE_DIR.parent.name == "web":
    WEB_DIR: Path = CURRENT_FILE_DIR.parent
    PROJECT_ROOT: Path = WEB_DIR.parent
    BACKEND_DIR: Path = CURRENT_FILE_DIR
else:
    # Fallback anchor search upward for project root containing 'web' and 'models'
    curr = CURRENT_FILE_DIR
    found_root: Path | None = None
    while curr.parent != curr:
        if (curr / "web").is_dir() and (curr / "models").is_dir():
            found_root = curr
            break
        curr = curr.parent

    if found_root is not None:
        PROJECT_ROOT = found_root
        WEB_DIR = PROJECT_ROOT / "web"
        BACKEND_DIR = WEB_DIR / "backend"
    else:
        # Fallback to current working directory
        cwd = Path.cwd().resolve()
        if (cwd / "web").is_dir():
            PROJECT_ROOT = cwd
            WEB_DIR = cwd / "web"
            BACKEND_DIR = WEB_DIR / "backend"
        else:
            PROJECT_ROOT = cwd
            WEB_DIR = cwd
            BACKEND_DIR = cwd

# Models directories
WEB_MODELS_DIR: Path = WEB_DIR / "models"
ROOT_MODELS_DIR: Path = PROJECT_ROOT / "models"
ROOT_MODEL_FILE: Path = PROJECT_ROOT / "yolo26n.pt"

# Dynamic Model Discovery Search Paths (in order of resolution priority)
# web/models/ is prioritized first so custom user uploads/drop-ins override repo defaults
MODEL_SEARCH_DIRS: List[Path] = [
    WEB_MODELS_DIR,
    ROOT_MODELS_DIR,
]
ADDITIONAL_MODEL_FILES: List[Path] = [
    ROOT_MODEL_FILE,
]

# Static assets and outputs
STATIC_DIR: Path = WEB_DIR / "static"
OUTPUTS_DIR: Path = WEB_DIR / "outputs"


def ensure_directories() -> None:
    """Ensure essential runtime directories exist."""
    WEB_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# 2. Server & Application Metadata
# ==============================================================================
APP_TITLE: str = "Hệ thống Nhận diện Máy bay không người lái (Anti-Drone)"
APP_DESCRIPTION: str = (
    "Ứng dụng phát hiện máy bay không người lái (drone) thời gian thực trên video và camera "
    "sử dụng mô hình YOLO và FastAPI."
)
APP_VERSION: str = "1.0.0"

DEFAULT_HOST: str = os.getenv("ANTI_DRONE_HOST", "127.0.0.1")
DEFAULT_PORT: int = int(os.getenv("ANTI_DRONE_PORT", "8000"))

# ==============================================================================
# 3. Model Engine Defaults & Thresholds
# ==============================================================================
SUPPORTED_MODEL_EXTENSIONS: Tuple[str, ...] = (".onnx", ".pt")

# The public/demo detector is intentionally restricted to this training batch.
# Keeping the allowlist explicit prevents legacy checkpoints in models/ from
# silently reappearing in the model selector after a restart.
FRESH_TRAINED_MODEL_ALLOWLIST = frozenset({
    "fresh_yolo26_img640_best.onnx",
    "drone-yolov8n-fresh-480.pt",
    "drone-yolov8n-fresh-640.pt",
    "drone-yolo11n-fresh-480.pt",
    "drone-yolo11n-fresh-640.pt",
    "drone-yolo26n-fresh-480.pt",
    "drone-yolo26n-fresh-640.pt",
})

# The fresh YOLOv8n 480 checkpoint has the strongest sampled detection coverage
# on the user's indoor/outdoor videos; yolo26 remains available in the selector.
DEFAULT_MODEL_NAME: str = "drone-yolov8n-fresh-480.pt"

FALLBACK_MODEL_NAMES: List[str] = [
    "drone-yolo26n-fresh-640.pt",
    "drone-yolo11n-fresh-640.pt",
    "drone-yolov8n-fresh-640.pt",
    "drone-yolo26n-fresh-480.pt",
    "drone-yolo11n-fresh-480.pt",
    "drone-yolov8n-fresh-480.pt",
]

DEFAULT_CONF_THRESHOLD: float = 0.25
DEFAULT_IOU_THRESHOLD: float = 0.45

CONF_MIN: float = 0.05
CONF_MAX: float = 1.00
IOU_MIN: float = 0.10
IOU_MAX: float = 0.95

# ==============================================================================
# 4. Video & Camera Streaming Settings
# ==============================================================================
SUPPORTED_VIDEO_EXTENSIONS: Set[str] = {".mp4", ".avi", ".mkv", ".mov"}
MAX_UPLOAD_SIZE_MB: int = 500
MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# FourCC codec for video export on Windows (OpenCV)
VIDEO_EXPORT_CODEC: str = "mp4v"

# Frame rate limits
WEBCAM_TARGET_FPS: float = 15.0
STREAM_MJPEG_MAX_FPS: float = 30.0

# ==============================================================================
# 5. Vietnamese UI Model Catalog & Localization Dictionary
# ==============================================================================
KNOWN_MODELS_METADATA: Dict[str, Dict[str, Any]] = {
    "yolov8n-drone-480.onnx": {
        "label": "YOLOv8n Drone 480 (Nhanh - Khuyên dùng)",
        "badge": "Nhanh - Khuyên dùng",
        "tag": "Khuyên dùng",
        "speed_rank": "Nhanh (~6.0 FPS)",
        "description": "Mô hình YOLOv8n huấn luyện chuyên biệt phát hiện drone, độ phân giải 480p, tối ưu tốc độ thời gian thực trên CPU.",
        "recommended": True,
        "target_resolution": 480,
        "task": "detect",
        "expected_classes": ["drone"],
    },
    "yolov8n-drone-640.onnx": {
        "label": "YOLOv8n Drone 640 (Độ nét cao)",
        "badge": "Độ nét cao",
        "tag": "Độ nét cao",
        "speed_rank": "Tiêu chuẩn (~4.3 FPS)",
        "description": "Mô hình YOLOv8n drone độ phân giải 640p tiêu chuẩn, độ chính xác cao đối với mục tiêu xa và nhỏ.",
        "recommended": False,
        "target_resolution": 640,
        "task": "detect",
        "expected_classes": ["drone"],
    },
    "yolov8n-drone-best.onnx": {
        "label": "YOLOv8n Drone Best (Trọng số tối ưu)",
        "badge": "Trọng số tối ưu",
        "tag": "Tối ưu",
        "speed_rank": "Tiêu chuẩn (~4.3 FPS)",
        "description": "Trọng số tốt nhất đạt được trong quá trình huấn luyện YOLOv8n trên tập dữ liệu drone.",
        "recommended": False,
        "target_resolution": 640,
        "task": "detect",
        "expected_classes": ["drone"],
    },
    "yolo26n-drone-480.onnx": {
        "label": "YOLO26n Drone 480",
        "badge": "Thế hệ mới 480p",
        "tag": "Thử nghiệm",
        "speed_rank": "Nhanh (~6.4 FPS)",
        "description": "Mô hình thế hệ mới YOLO26n huấn luyện phát hiện drone, độ phân giải 480p, tốc độ suy luận nhanh.",
        "recommended": False,
        "target_resolution": 480,
        "task": "detect",
        "expected_classes": ["drone"],
    },
    "yolo26n-drone-640.onnx": {
        "label": "YOLO26n Drone 640 (Độ nét cao)",
        "badge": "Thế hệ mới 640p",
        "tag": "Thử nghiệm",
        "speed_rank": "Tiêu chuẩn (~4.3 FPS)",
        "description": "Mô hình YOLO26n drone độ phân giải 640p, cân bằng giữa độ chính xác nhận diện và kiến trúc mạng mới.",
        "recommended": False,
        "target_resolution": 640,
        "task": "detect",
        "expected_classes": ["drone"],
    },
    "yolo11n-drone-480.onnx": {
        "label": "YOLO11n Drone 480 (Tốc độ cao)",
        "badge": "Tốc độ cao",
        "tag": "Tốc độ cao",
        "speed_rank": "Nhanh (~6.4 FPS)",
        "description": "Mô hình YOLO11n drone tối ưu 480p, tốc độ cao trên CPU (~6.4 FPS), độ ổn định nhận diện tốt.",
        "recommended": False,
        "target_resolution": 480,
        "task": "detect",
        "expected_classes": ["drone"],
    },
    "yolo11n-drone-640.onnx": {
        "label": "YOLO11n Drone 640 (Độ nét cao)",
        "badge": "Độ nét cao",
        "tag": "Độ nét cao",
        "speed_rank": "Tiêu chuẩn (~4.3 FPS)",
        "description": "Mô hình YOLO11n drone độ phân giải 640p, phát hiện chi tiết vật thể bay tầm xa.",
        "recommended": False,
        "target_resolution": 640,
        "task": "detect",
        "expected_classes": ["drone"],
    },
    "yolo26n.pt": {
        "label": "YOLO26n COCO (Mặc định - 80 lớp)",
        "badge": "Mặc định - 80 lớp",
        "tag": "Gốc COCO",
        "speed_rank": "Cơ bản (~4.1 FPS)",
        "description": "Mô hình gốc YOLO26n tiền huấn luyện trên tập dữ liệu COCO (80 lớp đối tượng tổng quát, bao gồm người, xe, chim...).",
        "recommended": False,
        "target_resolution": 640,
        "task": "detect",
        "expected_classes": ["80 classes COCO"],
    },
}


def generate_fallback_metadata(filename: str, file_path: Path, num_classes: int = 1) -> Dict[str, Any]:
    """
    Intelligently generate friendly Vietnamese metadata for any newly dropped-in
    .onnx or .pt model file without modifying any code.
    """
    ext = file_path.suffix.lower().lstrip(".")
    stem = file_path.stem

    # Detect resolution hint in filename
    resolution = 640
    if "480" in stem:
        resolution = 480
    elif "640" in stem:
        resolution = 640
    elif "320" in stem:
        resolution = 320

    # Detect drone specialization
    is_drone = "drone" in stem.lower()
    clean_title = stem.replace("-", " ").replace("_", " ").title()

    if is_drone:
        label = f"{clean_title} ({ext.upper()} - Chuyên Drone)"
        badge = "Drone Tùy biến"
        tag = "Drone"
        desc = f"Mô hình nhận diện drone tùy biến ({ext.upper()}) tự động nạp từ thư mục models."
        expected_classes = ["drone"]
    else:
        label = f"{clean_title} ({ext.upper()} - {num_classes} lớp)"
        badge = f"{ext.upper()} {num_classes} lớp"
        tag = "Tùy biến"
        desc = f"Mô hình đối tượng tổng quát ({ext.upper()}) tự động nạp từ thư mục models."
        expected_classes = [f"{num_classes} lớp đối tượng"]

    return {
        "label": label,
        "badge": badge,
        "tag": tag,
        "speed_rank": "Tự động phát hiện",
        "description": desc,
        "recommended": False,
        "target_resolution": resolution,
        "task": "detect",
        "expected_classes": expected_classes,
    }


# ==============================================================================
# 6. Vietnamese System Status & UI Dictionaries
# ==============================================================================
STATUS_MESSAGES = {
    "ready": "Sẵn sàng nhận diện",
    "processing": "Đang xử lý khung hình",
    "completed": "Đã hoàn thành nhận diện",
    "error": "Lỗi trong quá trình xử lý",
    "model_swapped": "Đã chuyển đổi mô hình thành công",
}

CLASS_NAME_VIETNAMESE = {
    "drone": "Drone (Máy bay không người lái)",
    "person": "Người",
    "bicycle": "Xe đạp",
    "car": "Ô tô",
    "motorcycle": "Xe máy",
    "airplane": "Máy bay",
    "bus": "Xe buýt",
    "train": "Tàu hỏa",
    "truck": "Xe tải",
    "boat": "Thuyền",
    "bird": "Chim",
}
