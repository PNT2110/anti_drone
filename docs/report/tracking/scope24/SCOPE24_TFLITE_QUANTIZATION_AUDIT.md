# Scope 24 — TFLite quantization audit

| Model | Path | Classification | Probe invoke | SHA-256 |
|---|---|---|---|---|
| scope18-yolov8n-480 | T1 | RUNTIME_INVOKE_BLOCKED | BLOCKED | 1911adc2e97c297e04ed49ced3d9bf5ed56f621d2db45c2824f202609443d72e |
| scope18-yolov8n-480 | T2 | FULL_INTEGER_INT8 | PASS | 0244c84fe5687d1dc3dd662448eb53ead79f481331cfd4451932697dccbcf119 |
| scope18-yolov8n-640 | T1 | RUNTIME_INVOKE_BLOCKED | BLOCKED | 94b62f804c0b6fb577b7de51f8441a006a17f4d3f8e92557dba157687c809111 |
| scope18-yolov8n-640 | T2 | MISSING | N/A | N/A |

T1/T2 valid artifacts use `int8` input/output tensors and quantized Conv operators. T1 input scale was `0.0039215689`, zero-point `-128`; output scales were `1.9316361` (480) and `2.5554228` (640), producing the T1 `LOGISTIC` runtime block.

T2 v8n-480 loaded and invoked as full integer, but its output scale `1.9316361` quantized the confidence row to zero on the diagnostic inputs. This is a real contract/parity failure, not a relaxed gate.
