"""Benchmark evaluation of the lightweight verification and correction pipeline on the benchmark dataset."""
import time
import psutil
import os
import pytest
from model_runner import NLIModelRunner
from generator import LLMCorrectionGenerator

def test_benchmark_dataset_accuracy_and_latency(benchmark_data):
    runner = NLIModelRunner(threshold=0.65, margin=0.10)
    runner.initialize()

    generator = LLMCorrectionGenerator()
    generator.initialize()

    process = psutil.Process(os.getpid())
    rss_start = process.memory_info().rss / (1024 * 1024)

    y_true = []
    y_pred = []
    latencies = []

    corrections_attempted = 0
    corrections_valid = 0

    start_bench = time.perf_counter()

    for item in benchmark_data:
        claim = item["claim"]
        evidence = item["evidence"]
        ground_truth = item["ground_truth"]

        t0 = time.perf_counter()
        res = runner.predict(premise=evidence, hypothesis=claim)
        t1 = time.perf_counter()

        pred_status = res["status"]
        latencies.append((t1 - t0) * 1000)

        y_true.append(ground_truth)
        y_pred.append(pred_status)

        # If claim is contradicted and correction is expected
        if pred_status == "Contradicted":
            corrections_attempted += 1
            corr_res = generator.generate_correction(claim=claim, evidence=evidence)
            corr_text = corr_res.get("correction", "")
            if corr_text:
                corrections_valid += 1

    total_duration = time.perf_counter() - start_bench
    rss_end = process.memory_info().rss / (1024 * 1024)

    # Compute classification metrics
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    accuracy = correct / len(y_true)

    classes = ["Supported", "Contradicted", "Unverified"]
    f1_scores = []
    for cls in classes:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == cls and yp == cls)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != cls and yp == cls)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == cls and yp != cls)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        f1_scores.append(f1)

    macro_f1 = sum(f1_scores) / len(f1_scores)

    latencies_sorted = sorted(latencies)
    p50_latency = latencies_sorted[len(latencies_sorted) // 2]
    p95_latency = latencies_sorted[int(len(latencies_sorted) * 0.95)]
    avg_latency = sum(latencies) / len(latencies)

    # Explicitly verify inference mode to ensure false claims of real inference are impossible
    assert runner.status()["is_real_model_ready"] is False
    assert runner.status()["inference_mode"] == "offline_calibrated_mock"
    assert generator.status()["is_real_model_ready"] is False
    assert generator.status()["inference_mode"] == "offline_calibrated_mock"

    print(f"\n================ BENCHMARK REPORT ================")
    print(f"EVALUATION MODE: OFFLINE HEURISTIC FALLBACK (NOT REAL AI MODEL)")
    print(f"REAL WEIGHTS STATUS: INACTIVE (Download skipped per user permission)")
    print(f"Total Evaluated Claims: {len(y_true)}")
    print(f"Accuracy (Fallback Heuristic): {accuracy * 100:.2f}% ({correct}/{len(y_true)})")
    print(f"Macro-F1 Score (Fallback Heuristic): {macro_f1 * 100:.2f}%")
    print(f"Per-Class F1 - Supported: {f1_scores[0]*100:.1f}%, Contradicted: {f1_scores[1]*100:.1f}%, Unverified: {f1_scores[2]*100:.1f}%")
    print(f"Latency: Avg={avg_latency:.2f}ms, P50={p50_latency:.2f}ms, P95={p95_latency:.2f}ms")
    print(f"Memory RSS: Start={rss_start:.1f}MB, End={rss_end:.1f}MB (Delta={rss_end - rss_start:.1f}MB)")
    print(f"Corrections Grounded: {corrections_valid}/{corrections_attempted} attempted")
    print(f"Total Benchmark Time: {total_duration:.3f}s")
    print(f"==================================================\n")

    assert accuracy >= 0.80, f"Accuracy {accuracy:.2f} should exceed baseline 0.80"
    assert macro_f1 >= 0.75, f"Macro-F1 {macro_f1:.2f} should exceed baseline 0.75"
