# Scope 25 — Freeze decision

The predeclared primary candidate was frozen after the Scope 25R reproduction gate:

`FP32_NCNN_CANDIDATE_FROZEN`

Selected deployment candidate: `YOLOv8n-480 / NCNN / FP32 / 480`.

Evidence used was limited to the frozen VAL metrics, Scope 20 parity, Scope 21 Pi benchmark, and the Scope 25R Pi reproduction. No TEST evaluation was performed. The candidate retains VAL mAP50-95 `0.62836`, VAL recall `0.98689`, historical Scope 21 FPS `22.493`, and Scope 25R mean derived FPS `23.1218`. The reproduction had 8/8 parity PASS and no throttling.

This is a deployment-candidate freeze under current project constraints, not a claim of absolute generalization superiority. Scope 26 must consume the exact freeze manifest rather than reselecting a model.
