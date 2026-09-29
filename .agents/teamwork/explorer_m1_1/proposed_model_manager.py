"""
web/backend/model_manager.py
Dynamic model discovery, thread-safe model caching, and runtime hot-swapping for YOLO backends.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

# Import configuration
try:
    from web.backend.config import (
        ADDITIONAL_MODEL_FILES,
        DEFAULT_CONF_THRESHOLD,
        DEFAULT_IOU_THRESHOLD,
        DEFAULT_MODEL_NAME,
        FALLBACK_MODEL_NAMES,
        KNOWN_MODELS_METADATA,
        MODEL_SEARCH_DIRS,
        SUPPORTED_MODEL_EXTENSIONS,
        ensure_directories,
        generate_fallback_metadata,
    )
except ImportError:
    try:
        from backend.config import (
            ADDITIONAL_MODEL_FILES,
            DEFAULT_CONF_THRESHOLD,
            DEFAULT_IOU_THRESHOLD,
            DEFAULT_MODEL_NAME,
            FALLBACK_MODEL_NAMES,
            KNOWN_MODELS_METADATA,
            MODEL_SEARCH_DIRS,
            SUPPORTED_MODEL_EXTENSIONS,
            ensure_directories,
            generate_fallback_metadata,
        )
    except ImportError:
        from config import (
            ADDITIONAL_MODEL_FILES,
            DEFAULT_CONF_THRESHOLD,
            DEFAULT_IOU_THRESHOLD,
            DEFAULT_MODEL_NAME,
            FALLBACK_MODEL_NAMES,
            KNOWN_MODELS_METADATA,
            MODEL_SEARCH_DIRS,
            SUPPORTED_MODEL_EXTENSIONS,
            ensure_directories,
            generate_fallback_metadata,
        )

# Import Detector & DetectionResult
try:
    from web.backend.detector import DetectionResult, YOLODetector
except ImportError:
    try:
        from backend.detector import DetectionResult, YOLODetector
    except ImportError:
        try:
            from detector import DetectionResult, YOLODetector
        except ImportError:
            # Fallback mock for standalone testing when detector.py is not yet generated
            YOLODetector = None
            DetectionResult = None

logger = logging.getLogger("anti_drone.model_manager")


# ==============================================================================
# Custom Exceptions
# ==============================================================================
class ModelManagerError(Exception):
    """Base exception for ModelManager operations."""
    pass


class ModelNotFoundError(ModelManagerError):
    """Raised when a requested model is not found in discovered models."""
    pass


class ModelLoadError(ModelManagerError):
    """Raised when loading or warming up a model fails."""
    pass


class NoModelsAvailableError(ModelManagerError):
    """Raised when no compatible models are found anywhere on disk."""
    pass


# ==============================================================================
# ModelManager Implementation
# ==============================================================================
class ModelManager:
    """
    Thread-safe model discovery, caching, hot-swapping, and inference manager.
    Coordinates between FastAPI routes/WebSockets and the underlying YOLO detector engine.
    """

    def __init__(
        self,
        auto_init: bool = True,
        default_model_name: Optional[str] = None,
        lazy_load: bool = False,
    ) -> None:
        self._lock = threading.RLock()
        self._models_metadata: Dict[str, Dict[str, Any]] = {}
        self._detector_cache: Dict[str, Any] = {}
        self._active_model_id: Optional[str] = None
        self._active_detector: Optional[Any] = None

        self.default_model_name = default_model_name or DEFAULT_MODEL_NAME

        # Ensure runtime directories exist
        ensure_directories()

        if auto_init:
            self.discover_models()
            if not lazy_load and self._models_metadata:
                self._initialize_default_model()

    # --------------------------------------------------------------------------
    # Model Discovery & Catalog
    # --------------------------------------------------------------------------
    def discover_models(self, force_rescan: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Dynamically scan models directory and root files for supported .onnx and .pt models.
        Thread-safe. Deduplicates models by filename, with earlier search directories having precedence.
        """
        with self._lock:
            if self._models_metadata and not force_rescan:
                return self._models_metadata

            discovered: Dict[str, Dict[str, Any]] = {}

            # 1. Search designated model directories in priority order
            for search_dir in MODEL_SEARCH_DIRS:
                if not search_dir.exists() or not search_dir.is_dir():
                    continue

                for ext in SUPPORTED_MODEL_EXTENSIONS:
                    for file_path in sorted(search_dir.glob(f"*{ext}")):
                        model_id = file_path.name
                        if model_id in discovered:
                            continue  # Higher priority directory already registered this filename

                        meta = self._build_model_metadata(model_id, file_path)
                        if meta is not None:
                            discovered[model_id] = meta

            # 2. Search individual root model files
            for file_path in ADDITIONAL_MODEL_FILES:
                if file_path.exists() and file_path.is_file():
                    model_id = file_path.name
                    if model_id not in discovered and file_path.suffix.lower() in SUPPORTED_MODEL_EXTENSIONS:
                        meta = self._build_model_metadata(model_id, file_path)
                        if meta is not None:
                            discovered[model_id] = meta

            self._models_metadata = discovered
            logger.info("Model discovery completed. Found %d valid models.", len(discovered))
            return self._models_metadata

    def _build_model_metadata(self, model_id: str, file_path: Path) -> Optional[Dict[str, Any]]:
        """Construct normalized metadata dictionary for a discovered model file."""
        try:
            stat = file_path.stat()
            if stat.st_size <= 0:
                logger.warning("Skipping empty model file: %s", file_path)
                return None

            size_mb = round(stat.st_size / (1024 * 1024), 2)
            fmt = file_path.suffix.lower().lstrip(".")

            # Fetch predefined or dynamically generated metadata
            if model_id in KNOWN_MODELS_METADATA:
                base_meta = dict(KNOWN_MODELS_METADATA[model_id])
            else:
                base_meta = generate_fallback_metadata(model_id, file_path)

            is_drone = (
                "drone" in model_id.lower()
                or base_meta.get("expected_classes") == ["drone"]
            )

            # Determine default classes mapping
            if is_drone:
                classes_map = {0: "drone"}
                num_classes = 1
            elif model_id == "yolo26n.pt":
                classes_map = {i: f"coco_class_{i}" for i in range(80)}
                num_classes = 80
            else:
                classes_map = {0: "object"}
                num_classes = 1

            return {
                "id": model_id,
                "name": base_meta["label"],
                "filename": model_id,
                "path": str(file_path.resolve()),
                "format": fmt,
                "size_mb": size_mb,
                "task": base_meta.get("task", "detect"),
                "num_classes": num_classes,
                "classes": classes_map,
                "label": base_meta["label"],
                "badge": base_meta["badge"],
                "tag": base_meta.get("tag", "Mô hình"),
                "speed_rank": base_meta.get("speed_rank", "Tiêu chuẩn"),
                "description": base_meta["description"],
                "target_resolution": base_meta.get("target_resolution", 640),
                "is_drone_model": is_drone,
                "recommended": base_meta.get("recommended", False),
                "is_active": (model_id == self._active_model_id),
            }
        except Exception as e:
            logger.error("Failed to build metadata for model '%s': %s", model_id, e)
            return None

    def list_models(self) -> List[Dict[str, Any]]:
        """
        Return sorted list of all available models with UI metadata and active status.
        Priority sorting: Recommended first -> Drone models -> Alphabetical.
        """
        with self._lock:
            if not self._models_metadata:
                self.discover_models()

            models_list = []
            for m_id, m_data in self._models_metadata.items():
                item = dict(m_data)
                item["is_active"] = (m_id == self._active_model_id)
                models_list.append(item)

            # Sort: recommended first, then drone models, then filename
            models_list.sort(
                key=lambda x: (
                    0 if x.get("recommended") else 1,
                    0 if x.get("is_drone_model") else 1,
                    x.get("filename", "")
                )
            )
            return models_list

    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Return metadata for a specific model ID. Raises ModelNotFoundError if missing."""
        with self._lock:
            if model_id not in self._models_metadata:
                self.discover_models(force_rescan=True)

            if model_id not in self._models_metadata:
                raise ModelNotFoundError(f"Mô hình '{model_id}' không tồn tại trong danh mục hệ thống.")

            info = dict(self._models_metadata[model_id])
            info["is_active"] = (model_id == self._active_model_id)
            return info

    # --------------------------------------------------------------------------
    # Model Hot-Swapping & Caching
    # --------------------------------------------------------------------------
    def set_active_model(self, model_id: str) -> bool:
        """
        Thread-safe hot-swap active model at runtime.
        Caches instantiated detectors to achieve zero-latency subsequent swaps.
        Raises ModelNotFoundError or ModelLoadError on failure, leaving prior active model untouched.
        """
        with self._lock:
            if model_id == self._active_model_id and self._active_detector is not None:
                return True

            if model_id not in self._models_metadata:
                self.discover_models(force_rescan=True)

            if model_id not in self._models_metadata:
                raise ModelNotFoundError(
                    f"Không tìm thấy mô hình '{model_id}'. Vui lòng kiểm tra thư mục 'models/'."
                )

            # Check in-memory detector cache
            if model_id in self._detector_cache:
                self._active_detector = self._detector_cache[model_id]
                self._active_model_id = model_id
                logger.info("Swapped to cached model: %s", model_id)
                return True

            # Instantiate and warmup new detector
            model_info = self._models_metadata[model_id]
            model_path = model_info["path"]

            try:
                detector = self._create_detector(model_path)
            except Exception as e:
                logger.error("Failed to load model '%s': %s", model_id, e)
                raise ModelLoadError(
                    f"Lỗi khởi tạo mô hình '{model_id}': {str(e)}"
                ) from e

            # Update cache and active state
            self._detector_cache[model_id] = detector
            self._active_detector = detector
            self._active_model_id = model_id

            # Update class dictionary in metadata from loaded detector if available
            if hasattr(detector, "names") and isinstance(detector.names, dict):
                self._models_metadata[model_id]["classes"] = detector.names
                self._models_metadata[model_id]["num_classes"] = len(detector.names)

            logger.info("Successfully loaded and activated model: %s", model_id)
            return True

    def _create_detector(self, model_path: Union[str, Path]) -> Any:
        """Helper to instantiate YOLODetector or fallback YOLO."""
        global YOLODetector
        if YOLODetector is None:
            try:
                from web.backend.detector import YOLODetector as YD
                YOLODetector = YD
            except ImportError:
                try:
                    from backend.detector import YOLODetector as YD
                    YOLODetector = YD
                except ImportError:
                    from detector import YOLODetector as YD
                    YOLODetector = YD

        return YOLODetector(model_path=model_path, warmup=True)

    def _initialize_default_model(self) -> None:
        """Initialize default or fallback model upon startup."""
        candidates = [self.default_model_name] + FALLBACK_MODEL_NAMES
        for candidate in candidates:
            if candidate in self._models_metadata:
                try:
                    self.set_active_model(candidate)
                    logger.info("Default model initialized: %s", candidate)
                    return
                except Exception as e:
                    logger.warning("Could not initialize candidate model '%s': %s", candidate, e)

        # Fallback to first discovered model
        if self._models_metadata:
            first_model = next(iter(self._models_metadata.keys()))
            try:
                self.set_active_model(first_model)
                logger.info("Fallback model initialized: %s", first_model)
                return
            except Exception as e:
                logger.error("Could not initialize first model '%s': %s", first_model, e)

        raise NoModelsAvailableError("Không có mô hình YOLO (.onnx hoặc .pt) nào khả dụng trong hệ thống.")

    # --------------------------------------------------------------------------
    # Active Model Accessors & Inference
    # --------------------------------------------------------------------------
    def get_active_model(self) -> Tuple[str, Any]:
        """
        Return tuple of (active_model_id, active_detector).
        Ensures a model is loaded if none is currently active.
        """
        with self._lock:
            if self._active_detector is None or self._active_model_id is None:
                self._initialize_default_model()
            return self._active_model_id, self._active_detector

    def get_active_model_id(self) -> str:
        """Return currently active model identifier."""
        with self._lock:
            if self._active_model_id is None:
                self._initialize_default_model()
            return self._active_model_id

    def get_active_model_info(self) -> Dict[str, Any]:
        """Return metadata dictionary of active model."""
        with self._lock:
            active_id = self.get_active_model_id()
            return self.get_model_info(active_id)

    def predict(
        self,
        image: np.ndarray,
        conf: float = DEFAULT_CONF_THRESHOLD,
        iou: float = DEFAULT_IOU_THRESHOLD,
        draw: bool = True,
        draw_fps: bool = False,
    ) -> Any:
        """
        Run object detection on an input BGR image frame using the active model.
        Thread-safe: executes under re-entrant lock or detector-level lock.
        """
        with self._lock:
            if self._active_detector is None:
                self._initialize_default_model()
            detector = self._active_detector

        return detector.detect(
            frame=image,
            conf=conf,
            iou=iou,
            draw=draw,
            draw_fps=draw_fps,
        )

    # --------------------------------------------------------------------------
    # Cache Management & Diagnostics
    # --------------------------------------------------------------------------
    def clear_cache(self, keep_active: bool = True) -> int:
        """
        Evict inactive models from in-memory cache to release RAM.
        Returns the number of evicted detector instances.
        """
        with self._lock:
            keys_to_evict = [
                k for k in self._detector_cache.keys()
                if not (keep_active and k == self._active_model_id)
            ]
            for k in keys_to_evict:
                del self._detector_cache[k]

            logger.info("Evicted %d models from memory cache.", len(keys_to_evict))
            return len(keys_to_evict)

    def get_system_status(self) -> Dict[str, Any]:
        """Return diagnostic status of ModelManager."""
        with self._lock:
            return {
                "active_model_id": self._active_model_id,
                "cached_models": list(self._detector_cache.keys()),
                "total_discovered_models": len(self._models_metadata),
                "cache_size": len(self._detector_cache),
            }


# ==============================================================================
# Global Singleton Accessor
# ==============================================================================
_manager_instance: Optional[ModelManager] = None
_instance_lock = threading.Lock()


def get_model_manager(default_model_name: Optional[str] = None) -> ModelManager:
    """
    Thread-safe double-checked singleton accessor for ModelManager.
    Ensures a single unified instance is shared across all FastAPI endpoints,
    WebSockets, and background video processing workers.
    """
    global _manager_instance
    if _manager_instance is None:
        with _instance_lock:
            if _manager_instance is None:
                _manager_instance = ModelManager(
                    auto_init=True,
                    default_model_name=default_model_name,
                    lazy_load=False,
                )
    return _manager_instance
