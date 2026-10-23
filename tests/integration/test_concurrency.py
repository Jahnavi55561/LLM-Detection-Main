"""Integration tests for concurrency controls, semaphores, and worker pools."""
import sys
import os
import threading
import time

NLI_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "model-services", "nli-verification"))
if NLI_PATH not in sys.path:
    sys.path.insert(0, NLI_PATH)

LLM_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "model-services", "llm-correction"))
if LLM_PATH not in sys.path:
    sys.path.insert(0, LLM_PATH)

from model_runner import NLIModelRunner
from generator import LLMCorrectionGenerator

def test_nli_semaphore_concurrency_control():
    # Configure a runner with max_concurrency=1
    runner = NLIModelRunner(max_concurrency=1)
    runner.initialize()

    results = []

    def slow_worker():
        res = runner.predict("Earth orbits the Sun.", "The Earth revolves around the Sun.")
        results.append(res)

    threads = [threading.Thread(target=slow_worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert len(results) == 3
    for res in results:
        assert res["status"] in ["Supported", "Contradicted", "Unverified"]

def test_llm_semaphore_concurrency_control():
    # Configure a generator with max_concurrency=1
    gen = LLMCorrectionGenerator(max_concurrency=1)
    gen.initialize()

    results = []

    def worker():
        res = gen.generate_correction("The Earth is flat.", "The Earth is spherical.")
        results.append(res)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert len(results) == 2
    for res in results:
        assert "correction" in res
