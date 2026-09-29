# BRIEFING — 2026-09-28T05:35:00Z

## Mission
Analyze and design architecture for web/backend/config.py and web/backend/model_manager.py for Milestone 1 (dynamic model discovery, friendly labels, thread-safe model caching/hot-swapping, error handling).

## 🔒 My Identity
- Archetype: explorer
- Roles: investigator, architect, designer
- Working directory: c:\Users\pnt21\OneDrive\Máy tính\DA_CNNC\anti_drone\.agents\teamwork\explorer_m1_1\
- Original parent: 595c75fc-66e7-4215-9d43-217f246c6ae5
- Milestone: Milestone 1 (Model Discovery & Hot-swapping Architecture)

## 🔒 Key Constraints
- Read-only investigation — do NOT modify project source files directly.
- All design proposals, specifications, and architecture must be written to `.agents/teamwork/explorer_m1_1/`.
- Provide concrete architecture, class definitions, and error handling for the implementation Worker.
- Dynamic model discovery must scan web/models/, root models/, and root yolo26n.pt for .onnx and .pt models.
- Thread-safe caching and hot-swapping using threading.Lock().
- Vietnamese UI labels with informative badges (e.g. Nhanh - Khuyên dùng, Độ nét cao, etc.).

## Current Parent
- Conversation ID: 595c75fc-66e7-4215-9d43-217f246c6ae5
- Updated: 2026-09-28T05:35:00Z

## Investigation State
- **Explored paths**:
  - `ORIGINAL_REQUEST.md`, `PROJECT.md`, `explorer_survey_2_gen2/handoff.md`
  - `explorer_m1_2/handoff.md` (detector interface and latency measurements)
  - `explorer_m1_3/progress.md` (unit test suite scope)
  - Model directory `models/` (7 ONNX models: yolov8n, yolo26n, yolo11n)
  - Root directory `yolo26n.pt`
- **Key findings**:
  - All 7 ONNX models in `models/` are single-class `{0: 'drone'}` and load via `YOLO(path, task='detect')`.
  - Baseline `yolo26n.pt` is 80-class COCO.
  - Model loading is lightweight (<1ms for ONNX session metadata, ~80ms for PT weights).
  - Priority discovery scanning `web/models/` before `models/` and root `yolo26n.pt` satisfies drop-in extensibility.
  - Re-entrant locking (`threading.RLock`) combined with in-memory caching guarantees race-condition-free runtime hot-swaps under heavy concurrent loads.
  - Standalone verification confirmed 100% test pass on discovery, priority sorting, Vietnamese labeling, hot-swapping, error handling, and thread safety.
- **Unexplored areas**: Milestone 2 video transcoding pipelines and Milestone 3 WebRTC webcam streaming.

## Key Decisions Made
- `DEFAULT_MODEL_NAME` set to `yolov8n-drone-480.onnx` (optimal ≥6.0 FPS CPU inference for live thesis defense).
- Designed complete reference implementations in `proposed_config.py` and `proposed_model_manager.py`.
- Designed robust path anchor discovery that resolves `PROJECT_ROOT` and `WEB_DIR` regardless of caller working directory.
- Created friendly Vietnamese localization dictionary with tags, badges, and speed ratings, plus fallback generator for custom dropped-in models.

## Artifact Index
- `DISPATCH.md` — Dispatch log with UTC timestamps
- `BRIEFING.md` — Persistent memory
- `progress.md` — Liveness heartbeat
- `proposed_config.py` — Complete proposed code for `web/backend/config.py`
- `proposed_model_manager.py` — Complete proposed code for `web/backend/model_manager.py`
- `handoff.md` — Authoritative 5-component handoff report
