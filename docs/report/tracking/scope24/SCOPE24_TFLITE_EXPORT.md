# Scope 24 — TFLite export

The predeclared paths were:

- T1: `onnx2tf --tflite_backend flatbuffer_direct --output_integer_quantized_tflite --input_quant_dtype int8 --output_quant_dtype int8`.
- T2: `onnx2tf --tflite_backend tf_converter` with the same full-integer settings, only after T1 runtime blocking.

T1 produced full-integer artifacts for both sizes, but a probe invocation failed at builtin `LOGISTIC` because the output scale was not `1/256`.

T2 produced a full-integer v8n-480 artifact. Its converter process did not terminate cleanly after writing it, so the artifact is diagnostic-only. T2 v8n-640 timed out at the bounded 180-second limit before writing a full-integer artifact.

No third converter path, version brute-force, NCNN E4+ experiment, or production overwrite was performed.
