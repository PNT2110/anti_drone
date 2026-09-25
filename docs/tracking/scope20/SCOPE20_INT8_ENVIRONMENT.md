# Scope 20 — INT8 environment investigation

Environment was not upgraded, downgraded, or installed into base/system Python. Versions before/after are `/run/media/pnt/APP/anti_drone/.runtime/scope20/environment_before.json` and `/run/media/pnt/APP/anti_drone/.runtime/scope20/environment_after.json`; the package set is unchanged and `tf_keras` is not importable.

Relevant versions: Torch 2.8.0+cu129, Ultralytics 8.4.125, TensorFlow CPU 2.20.0, LiteRT 2.2.0, onnx2tf 2.6.9, ONNX Runtime 1.26.0, NCNN 1.0.20260526.

The original Ultralytics TFLite route is blocked by `ScalingType` import incompatibility. The isolated onnx2tf flatbuffer-direct route can produce float32/float16 TFLite for `scope18-yolov8n-480`, but it mutates its input ONNX file; Scope 20 therefore copies each input first and records before/after hashes. The Scope 19 source hash remains unchanged.

The alternate `tf_converter` route is also blocked because optional `tf_keras` is absent. No package installation was performed.
