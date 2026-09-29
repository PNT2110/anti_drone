"""
stress_test_m1.py
Empirical Adversarial Stress & Concurrency Verification Suite for Milestone 1.

Tasks:
1. Rapid concurrent model hot-swapping across multiple threads while simultaneously
   calling predict() on synthetic frames. Assert 0 deadlocks, 0 crashes, 0 race conditions.
2. 50 continuous forward passes on CPU with memory usage tracking to confirm zero memory leakage.
3. Attempting to select invalid, non-existent, and directory traversal model names
   ('../../secret.pt', 'nonexistent.onnx'). Assert clean exception handling and model preservation.
"""

from __future__ import annotations

import concurrent.futures
import gc
import logging
import os
import sys
import threading
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import psutil

# Ensure web/ and project root are in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
WEB_DIR = PROJECT_ROOT / "web"

for p in (str(WEB_DIR), str(PROJECT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend import config
from backend.detector import DetectionResult, YOLODetector
from backend.model_manager import (
    ModelLoadError,
    ModelManager,
    ModelManagerError,
    ModelNotFoundError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("challenger_m1")


class AdversarialStressTest:
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.results: Dict[str, Any] = {}

    def run_all(self) -> bool:
        print("=" * 80)
        print("   EMPIRICAL ADVERSARIAL STRESS & CONCURRENCY VERIFICATION: MILESTONE 1")
        print("=" * 80)

        all_passed = True
        try:
            print("\n[CHALLENGE 1/3] Rapid Concurrent Model Hot-Swapping & Inference Stress...")
            c1_pass = self.test_concurrency_and_hotswap()
            all_passed = all_passed and c1_pass
        except Exception as e:
            logger.exception("Challenge 1 failed with unexpected exception: %s", e)
            all_passed = False

        try:
            print("\n[CHALLENGE 2/3] 50 Continuous Forward Passes CPU Memory Leakage Tracking...")
            c2_pass = self.test_memory_leakage_50_passes()
            all_passed = all_passed and c2_pass
        except Exception as e:
            logger.exception("Challenge 2 failed with unexpected exception: %s", e)
            all_passed = False

        try:
            print("\n[CHALLENGE 3/3] Path Traversal, Non-existent & Malformed Model Input Attacks...")
            c3_pass = self.test_path_traversal_and_invalid_models()
            all_passed = all_passed and c3_pass
        except Exception as e:
            logger.exception("Challenge 3 failed with unexpected exception: %s", e)
            all_passed = False

        print("\n" + "=" * 80)
        print("   CHALLENGER FINAL VERDICT & SUMMARY")
        print("=" * 80)
        for name, res in self.results.items():
            status = "PASS [OK]" if res["passed"] else "FAIL [CRITICAL]"
            print(f" - {name:<45}: {status}")
            if "details" in res:
                print(f"     Details: {res['details']}")

        verdict = "APPROVE" if all_passed else "REJECT"
        print(f"\nEXPLICIT VERDICT: {verdict}")
        print("=" * 80)
        return all_passed

    # --------------------------------------------------------------------------
    # CHALLENGE 1: Concurrency & Hot-swap
    # --------------------------------------------------------------------------
    def test_concurrency_and_hotswap(self) -> bool:
        manager = ModelManager()
        models_available = [m["name"] for m in manager.list_models()]
        print(f"   Available models for swapping: {models_available}")

        # Choose a set of models to alternate between
        swap_candidates = [m for m in ["yolov8n-drone-480.onnx", "yolo26n.pt", "yolo11n-drone-480.onnx"] if m in models_available]
        if len(swap_candidates) < 2:
            swap_candidates = models_available[:2]

        stop_event = threading.Event()
        inference_errors: List[Exception] = []
        swap_errors: List[Exception] = []
        inference_count = 0
        swap_count = 0
        count_lock = threading.Lock()

        # Synthetic frames with varied resolutions
        frames = [
            np.zeros((480, 640, 3), dtype=np.uint8),
            np.random.randint(0, 256, (360, 480, 3), dtype=np.uint8),
            np.ones((240, 320, 3), dtype=np.uint8) * 128,
        ]

        def inference_worker(worker_id: int):
            nonlocal inference_count
            f_idx = 0
            while not stop_event.is_set():
                try:
                    frame = frames[f_idx % len(frames)]
                    res = manager.predict(frame, conf=0.25, iou=0.45)
                    assert isinstance(res, DetectionResult), f"Worker {worker_id}: Invalid result type"
                    assert isinstance(res.boxes, list), f"Worker {worker_id}: boxes not a list"
                    assert res.annotated_frame.shape == frame.shape, f"Worker {worker_id}: frame shape mismatch"
                    with count_lock:
                        inference_count += 1
                except Exception as ex:
                    logger.error("Inference worker %d error: %s", worker_id, ex)
                    inference_errors.append(ex)
                f_idx += 1
                time.sleep(0.002)

        def swap_worker(worker_id: int):
            nonlocal swap_count
            s_idx = 0
            while not stop_event.is_set():
                target_model = swap_candidates[s_idx % len(swap_candidates)]
                try:
                    success = manager.set_active_model(target_model)
                    assert success is True, f"Swap worker {worker_id}: set_active_model returned False"
                    with count_lock:
                        swap_count += 1
                except Exception as ex:
                    logger.error("Swap worker %d error on '%s': %s", worker_id, target_model, ex)
                    swap_errors.append(ex)
                s_idx += 1
                time.sleep(0.03)

        num_inf_workers = 4
        num_swap_workers = 2
        stress_duration = 3.5  # seconds of continuous pounding

        t0 = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_inf_workers + num_swap_workers) as executor:
            inf_futures = [executor.submit(inference_worker, i) for i in range(num_inf_workers)]
            swap_futures = [executor.submit(swap_worker, i) for i in range(num_swap_workers)]

            time.sleep(stress_duration)
            stop_event.set()

            # Wait with strict timeout to detect any deadlock
            for f in concurrent.futures.as_completed(inf_futures + swap_futures, timeout=10.0):
                f.result()

        elapsed = time.perf_counter() - t0
        print(f"   [RESULT] Completed in {elapsed:.2f}s:")
        print(f"     - Completed inferences: {inference_count}")
        print(f"     - Completed model hot-swaps: {swap_count}")
        print(f"     - Inference exceptions: {len(inference_errors)}")
        print(f"     - Hot-swap exceptions: {len(swap_errors)}")

        passed = (len(inference_errors) == 0) and (len(swap_errors) == 0) and (inference_count > 20) and (swap_count > 5)
        self.results["1. Concurrency & Hot-Swapping Stress"] = {
            "passed": passed,
            "details": f"{inference_count} inferences, {swap_count} swaps, {len(inference_errors)} inf errors, {len(swap_errors)} swap errors",
        }
        return passed

    # --------------------------------------------------------------------------
    # CHALLENGE 2: 50 Forward Passes Memory Leak Tracking
    # --------------------------------------------------------------------------
    def test_memory_leakage_50_passes(self) -> bool:
        manager = ModelManager()
        # Ensure active model is yolov8n-drone-480.onnx
        manager.set_active_model("yolov8n-drone-480.onnx")

        # Synthetic test frame (480x640x3)
        np.random.seed(1337)
        frame = np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)

        # Warm up with 5 passes to reach steady state
        print("   Warming up engine (5 forward passes)...")
        for _ in range(5):
            manager.predict(frame)

        gc.collect()
        time.sleep(0.2)

        tracemalloc.start()
        base_rss_mb = self.process.memory_info().rss / (1024 * 1024)
        base_tm_current, _ = tracemalloc.get_traced_memory()
        base_tm_mb = base_tm_current / (1024 * 1024)

        print(f"   Baseline Memory: Process RSS = {base_rss_mb:.2f} MB | Traced Memory = {base_tm_mb:.2f} MB")

        total_passes = 50
        rss_samples: List[float] = []
        tm_samples: List[float] = []

        print(f"   Executing {total_passes} continuous forward passes on CPU...")
        t0 = time.perf_counter()
        for i in range(1, total_passes + 1):
            res = manager.predict(frame, conf=0.25, iou=0.45)
            assert isinstance(res, DetectionResult)

            if i % 10 == 0 or i == total_passes:
                current_rss = self.process.memory_info().rss / (1024 * 1024)
                cur_tm, _ = tracemalloc.get_traced_memory()
                current_tm_mb = cur_tm / (1024 * 1024)
                rss_samples.append(current_rss)
                tm_samples.append(current_tm_mb)
                print(f"     Pass {i:02d}/{total_passes}: RSS = {current_rss:.2f} MB (+{current_rss - base_rss_mb:+.2f} MB), Traced = {current_tm_mb:.2f} MB (+{current_tm_mb - base_tm_mb:+.2f} MB)")

        total_inference_time = time.perf_counter() - t0
        avg_latency_ms = (total_inference_time / total_passes) * 1000.0

        gc.collect()
        time.sleep(0.2)
        final_rss_mb = self.process.memory_info().rss / (1024 * 1024)
        final_tm_current, peak_tm = tracemalloc.get_traced_memory()
        final_tm_mb = final_tm_current / (1024 * 1024)
        tracemalloc.stop()

        rss_delta_mb = final_rss_mb - base_rss_mb
        tm_delta_mb = final_tm_mb - base_tm_mb

        print(f"   [RESULT] Completed 50 forward passes in {total_inference_time:.2f}s (Avg {avg_latency_ms:.1f}ms / pass):")
        print(f"     - Base RSS:  {base_rss_mb:.2f} MB")
        print(f"     - Final RSS: {final_rss_mb:.2f} MB (Delta: {rss_delta_mb:+.2f} MB)")
        print(f"     - Base Traced:  {base_tm_mb:.2f} MB")
        print(f"     - Final Traced: {final_tm_mb:.2f} MB (Delta: {tm_delta_mb:+.2f} MB)")

        # Leak criteria: Under 50 passes, memory growth should not exceed 25 MB on CPU
        # Python GC / ONNX Runtime buffers may have minor working set fluctuation (< 20MB)
        # But should not grow continuously with each iteration
        passed = rss_delta_mb < 25.0 and tm_delta_mb < 15.0
        self.results["2. 50 Continuous Passes Memory Leakage"] = {
            "passed": passed,
            "details": f"RSS delta: {rss_delta_mb:+.2f} MB, Traced delta: {tm_delta_mb:+.2f} MB, Avg latency: {avg_latency_ms:.1f}ms",
        }
        return passed

    # --------------------------------------------------------------------------
    # CHALLENGE 3: Path Traversal & Invalid Model Selection Attacks
    # --------------------------------------------------------------------------
    def test_path_traversal_and_invalid_models(self) -> bool:
        manager = ModelManager()
        initial_active = manager.get_active_model_id()
        print(f"   Initial active model: {initial_active}")

        attack_payloads = [
            ("../../secret.pt", "Directory traversal relative with pt extension"),
            ("..\\..\\secret.pt", "Windows directory traversal backslash"),
            ("../../../etc/passwd", "UNIX directory traversal"),
            ("nonexistent.onnx", "Non-existent model with valid extension"),
            ("invalid_format.txt", "Non-supported file extension"),
            ("   ", "Whitespace string"),
            ("", "Empty string"),
            ("C:\\Windows\\System32\\calc.exe", "Absolute path to executable"),
            ("models/../../yolo26n.pt", "Nested traversal attempt"),
            ("null\x00byte.onnx", "Null-byte injection"),
        ]

        test_frame = np.zeros((240, 320, 3), dtype=np.uint8)
        attack_results = []
        all_safe = True

        for payload, description in attack_payloads:
            active_before = manager.get_active_model_id()
            exception_raised = False
            caught_type = None

            try:
                manager.set_active_model(payload)
            except (ModelNotFoundError, ModelManagerError, KeyError, ValueError, FileNotFoundError) as ex:
                exception_raised = True
                caught_type = type(ex).__name__
            except Exception as unhandled:
                exception_raised = True
                caught_type = f"UNHANDLED: {type(unhandled).__name__}"
                all_safe = False

            # Check model preservation
            active_after = manager.get_active_model_id()
            preserved = (active_after == active_before)

            # Check that model remains operational
            try:
                test_res = manager.predict(test_frame)
                operational = isinstance(test_res, DetectionResult)
            except Exception as e:
                logger.error("Model failure after attack payload '%s': %s", payload, e)
                operational = False

            attack_passed = exception_raised and preserved and operational and (not str(caught_type).startswith("UNHANDLED"))
            attack_results.append((payload, description, caught_type, preserved, operational, attack_passed))
            print(f"     Payload: '{payload}' ({description})")
            print(f"       -> Exception: {caught_type} | Preserved: {preserved} | Operational: {operational} => {'SAFE' if attack_passed else 'VULNERABLE'}")
            if not attack_passed:
                all_safe = False

        self.results["3. Path Traversal & Invalid Input Attacks"] = {
            "passed": all_safe,
            "details": f"{sum(1 for a in attack_results if a[5])}/{len(attack_payloads)} attack vectors neutralized safely",
        }
        return all_safe


if __name__ == "__main__":
    tester = AdversarialStressTest()
    success = tester.run_all()
    sys.exit(0 if success else 1)
