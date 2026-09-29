# Anti-drone repository guide

Snapshot of branch main for PNT2110/anti_drone.

## 1. Mục tiêu dự án

Đây là pipeline phát hiện drone từ camera USB. Mô hình single-class với class 0 = drone. Training, evaluation và export chạy trên máy GPU; Raspberry Pi 5 4GB chỉ chạy preprocessing, inference CPU, tracking, overlay và logging. Repo không điều khiển GPIO, actuator, vũ khí hoặc dẫn đường.

## 2. Pipeline end-to-end

USB camera -> capture thread -> latest-frame queue -> letterbox 640x640 -> YOLO detector -> decode/confidence filtering -> NMS -> ByteTrackLite -> multi-frame alert state -> overlay và runtime log.

### Phase 00 - Repository baseline

Kiểm tra Python, package, CUDA/GPU, cấu trúc repo, archive dataset và test skeleton. Baseline dự kiến được ghi vào .runtime/baseline/ gồm system.json, python.json, cuda.json, repository.json và baseline_report.md.

### Phase 01 - Dataset ingestion và audit

Script: scripts/prepare_dataset.py. Source root: data/import_data_rar/. Pipeline inventory source, checksum SHA-256, quarantine archive tải dở, giải nén an toàn, tìm ảnh/label, deduplicate toàn cục, chuẩn hóa label YOLO và tạo split.

Split mục tiêu: train 70%, val 20%, test 10%. Toàn bộ sample hợp lệ của my_dataset bắt buộc nằm trong train. Split phải group-aware theo source/video/sequence, không có image/hash/frame overlap giữa các split.

Output: data/processed/drone-single-class/ gồm images/, labels/, data.yaml, manifest.json, split_registry.json, label_statistics.json và audit.json. Chỉ chuyển phase khi audit.json có status valid.

### Phase 02 - GPU training

Script: scripts/train_gpu.py. Baseline gồm yolov8n, yolov11n và yolo26n; mặc định input 640, 100 epochs, batch 8, workers 4, seed 42, device 0. Script yêu cầu CUDA, hỗ trợ resume từ last.pt, ghi provenance và lưu best.pt/last.pt, results.csv, plots và args.yaml.

### Phase 03 - Evaluation và model selection

Script: scripts/evaluate_phase3.py. Confidence sweep trên validation từ 0.05 đến 0.60, bước 0.05; matching IoU 0.50; NMS IoU 0.70. Có metrics precision, recall, F1, mAP50, mAP50-95, size-bin, negative-frame/video và threshold sweep. Threshold chỉ chọn trên validation; test chỉ mở sau khi candidate đã khóa. Model xếp hạng chủ yếu theo validation F1, sau đó recall và precision.

### Phase 04 - Export và runtime parity

Script: scripts/export_phase4.py. Model winner được export sang ONNX Runtime, NCNN và TFLite/LiteRT. Dùng representative parity set, so sánh output giữa PyTorch và ba runtime, ghi metadata.json, parity.json và SHA256SUMS. Acceptance gate yêu cầu confidence sai lệch không quá 0.05 và bbox sai lệch không quá 5 px.

### Phase 05 - Pi runtime

Core: src/anti_drone/runtime.py. run_phase5.py hỗ trợ replay và camera live. Frame camera BGR được letterbox, đổi sang RGB, BCHW, float32 0..1 rồi đưa vào backend đã chọn.

Các engine gồm OnnxEngine, NcnnEngine và LiteRTEngine. Output YOLO được decode thành xywh/xyxy, lọc confidence, chạy OpenCV NMS và khôi phục tọa độ về ảnh gốc.

ByteTrackLite match track bằng IoU; detection thấp nhất 0.10, threshold tạo track mới 0.25, match IoU 0.30, giữ track tối đa 15 frame. AlertState yêu cầu 3 hit trong 5 frame và cooldown 30 frame, tránh cảnh báo từ một frame đơn lẻ.

LatestFrame queue chỉ giữ frame mới nhất. Khi inference chậm, frame cũ bị bỏ để giới hạn latency và bộ nhớ. Camera runtime có reconnect, overlay, runtime.log, camera_report.json và đếm dropped frames.

### Phase 06 - Benchmark và release

Script: scripts/benchmark_phase6.py. Mỗi runtime dùng cùng model, input, parity set và threshold; warm-up 200 frame, đo 1000 frame. Ghi model-only/end-to-end latency, mean/p50/p95/p99, FPS, RSS, nhiệt độ, dropped frames và environment metadata. Camera sustained gate yêu cầu 1800 giây.

package_pi_release.py đóng gói bundle. promote_pi_release.py kiểm tra camera reports và benchmark. verify_phase4_to7.py audit checksum, bundle, replay, benchmark và dataset hash. finalize_phase4_to7.py tổng hợp release/handoff status.

### Phase 07 - Retraining và maintenance

Dataset v1 được freeze. Batch mới phải nằm trong data/incoming/batch_<YYYYMMDD>/, được review label, checksum, kiểm tra duplicate, tạo dataset version mới và so sánh với baseline. Chỉ export/benchmark/release lại nếu candidate không phá baseline.

## 3. Cấu trúc repository

- .github/workflows/ci.yml: CI hiện chỉ checkout và chạy python -m compileall -q src trên push/pull request.
- configs/datasets/drone-single-class.yaml: dataset config single-class; path hiện là placeholder /path/to/drone-single-class.
- configs/models/: yolo26n.yaml, yolov11n.yaml, yolov8n.yaml; hiện chủ yếu là placeholder.
- docs/phases/: runbook Phase 00 đến Phase 07 và acceptance gate.
- docs/DATASETS.md: chính sách source, class, split, duplicate và manifest.
- docs/PI5_EXECUTION_STATUS.md: log thực thi trên Pi, benchmark và evidence.
- docs/PI5_HANDOFF.md: hướng dẫn copy artifact, replay, camera và benchmark trên Pi.
- docs/REPOSITORY_LAYOUT.md, TRAINING.md, RESEARCH_PLAN.md: tài liệu tổng quan hiện còn ngắn.
- scripts/: prepare_dataset.py, train_gpu.py, evaluate_phase3.py, export_phase4.py, run_phase5.py, benchmark_phase6.py, package_pi_release.py, promote_pi_release.py, finalize_phase4_to7.py, verify_phase4_to7.py.
- src/anti_drone/runtime.py: detector runtime, preprocessing, decoder, NMS, backends, tracker, alert state và overlay.
- tests/test_runtime.py: test letterbox, decode bbox và alert sau ba hit.
- runs/detect/artifacts/experiments/...: experiment artifacts đang được commit gồm args.yaml và một số ảnh training.
- README.md: mô tả mục tiêu, kiến trúc, cách chạy Pi, training GPU, phase runbook và kết quả benchmark.
- pyproject.toml: package anti-drone version 0.1.0, Python >=3.11, source root src/.
- requirements.txt: NumPy, OpenCV, ONNX, ONNX Runtime, Ultralytics và NCNN.
- requirements-pi.txt: dependency runtime cho Pi, gồm OpenCV headless, ONNX Runtime, TFLite runtime và NCNN tùy kiến trúc.
- requirements-dev.txt: hiện chỉ include requirements.txt.
- environment.yml: Conda environment Python 3.11.
- .gitignore: loại data/, artifacts/, .runtime/, cache Python và virtualenv.
- yolo26n.pt: checkpoint được commit ở root.

## 4. Kết quả Pi được ghi trong evidence

Theo docs/PI5_EXECUTION_STATUS.md, benchmark Pi 5 4GB ở input 640 ghi nhận:

- ONNX: model-only 7.10 FPS, end-to-end 6.77 FPS, p95 154.81 ms, nhiệt độ tối đa 53.45 C.
- NCNN: model-only 14.20 FPS, end-to-end 12.85 FPS, p95 81.13 ms, RSS 211.6 MB, nhiệt độ 47.40 C.
- TFLite/LiteRT: model-only 7.76 FPS, end-to-end 7.35 FPS, p95 138.79 ms, RSS 296.2 MB, nhiệt độ 52.35 C.

NCNN là profile nhanh nhất theo số liệu hiện có.

## 5. Điểm cần đồng bộ hoặc cải thiện

1. README và PI5_EXECUTION_STATUS.md mô tả Phase 4-7 đã hoàn thành, nhưng runbook phase vẫn còn trạng thái TODO/BLOCKED ở một số phase.
2. README dùng lệnh anti-drone ..., nhưng pyproject.toml chưa khai báo console entry point; cách chạy chắc chắn hiện tại là python scripts/*.py.
3. train_gpu.py có đường dẫn checkpoint hard-code dưới /home/pnt/Desktop/antidrone/model/ nên chưa portable.
4. requirements-dev.txt chưa khai báo rõ pytest; CI cũng chưa chạy pytest.
5. environment.yml chưa mô tả đầy đủ PyTorch, CUDA, Ultralytics, ONNX hoặc NCNN.
6. Model YAML là placeholder; nhiều tham số thực tế nằm trong script hoặc Ultralytics checkpoint.
7. Một số script hard-code run name, artifact path và benchmark run ID.
8. data/, artifacts/ và .runtime/ bị gitignore, vì vậy evidence local/Pi không nhất thiết xuất hiện đầy đủ trên GitHub.
9. TFLite export phụ thuộc onnx2tf nhưng dependency này chưa được khai báo trực tiếp trong requirements.

## 6. Kết luận

Repo đã có khung đầy đủ của một ML deployment pipeline: dataset audit -> GPU training -> validation/model selection -> multi-runtime export -> parity -> Pi replay/camera -> benchmark -> release bundle -> independent verification -> maintenance. Phần cần ưu tiên hoàn thiện là CLI chính thức, config thật, CI test đầy đủ, loại bỏ hard-code path và đồng bộ trạng thái giữa README, phase runbook và evidence.
