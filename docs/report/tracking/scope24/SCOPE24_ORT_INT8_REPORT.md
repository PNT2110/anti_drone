# Scope 24 — ONNX Runtime INT8 secondary report

The single predeclared O1 method was static QDQ INT8, per-channel, MinMax calibration, exact 128-image TRAIN membership. Both generated graphs were rejected by the selected ORT runtime because their bias `DequantizeLinear` nodes used an unsupported `axis` attribute. No QOperator/per-tensor or other permutation was tried.

| Model | Status | Artifact SHA-256 | Error |
|---|---|---|---|
| scope18-yolov8n-480 | ORT_INT8_BLOCKED | 26acbbb8cd3ddff954c0231c005bc741361260dfe5abddf1164e786012454204 | InvalidGraph('[ONNXRuntimeError] : 10 : INVALID_GRAPH : Load model from /run/media/pnt/APP/anti_drone/artifacts/exports/scope24/scope18-yolov8n-480/O1/model_qdq_int8.onnx failed:This is an invalid model. In Node, ("model.0.conv.bias_DequantizeLinear", DequantizeLinear, "", -1) : ("model.0.conv.bias_quantized": tensor(int32),"model.0.conv.bias_quantized_scale": tensor(float),"model.0.conv.bias_quantized_zero_point": tensor(int32),) -> ("model.0.conv.bias",) , Error Unrecognized attribute: axis for operator DequantizeLinear') |
| scope18-yolov8n-640 | ORT_INT8_BLOCKED | 6db11be5a6d3aeaabd9f3e74a80d255f494efd8db568ce52028896076138966f | InvalidGraph('[ONNXRuntimeError] : 10 : INVALID_GRAPH : Load model from /run/media/pnt/APP/anti_drone/artifacts/exports/scope24/scope18-yolov8n-640/O1/model_qdq_int8.onnx failed:This is an invalid model. In Node, ("model.0.conv.bias_DequantizeLinear", DequantizeLinear, "", -1) : ("model.0.conv.bias_quantized": tensor(int32),"model.0.conv.bias_quantized_scale": tensor(float),"model.0.conv.bias_quantized_zero_point": tensor(int32),) -> ("model.0.conv.bias",) , Error Unrecognized attribute: axis for operator DequantizeLinear') |

Conclusion: `ORT_INT8_BLOCKED`.
