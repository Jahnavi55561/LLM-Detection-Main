"""End-to-end tests for live model inference on physical hardware.

These tests evaluate real model weights when provisioned:
- NLI: cross-encoder/nli-MiniLM2-L6-H768 (PyTorch or ONNX Runtime)
- LLM: Qwen/Qwen2.5-0.5B-Instruct (GGUF or PyTorch)

When weights are not found on disk, tests cleanly skip with an informative reason
to prevent reporting false verification or degraded fallback metrics as real model performance.
"""
import os
import sys
import pytest

# Ensure model services are importable
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NLI_PATH = os.path.join(ROOT_DIR, "model-services", "nli-verification")
LLM_PATH = os.path.join(ROOT_DIR, "model-services", "llm-correction")

if NLI_PATH not in sys.path:
    sys.path.insert(0, NLI_PATH)
if LLM_PATH not in sys.path:
    sys.path.insert(0, LLM_PATH)

from model_runner import NLIModelRunner
from generator import LLMCorrectionGenerator


# ==============================================================================
# Helper fixtures / checks
# ==============================================================================

def get_real_nli_runner():
    runner = NLIModelRunner()
    runner.initialize()
    if not runner.is_real_model:
        pytest.skip(
            "SKIPPED: Real NLI model weights not found on disk. "
            "Model 'cross-encoder/nli-MiniLM2-L6-H768' must be cached or exported to ONNX "
            "to run genuine hardware inference tests."
        )
    return runner


def get_real_llm_generator():
    generator = LLMCorrectionGenerator()
    generator.initialize()
    if not generator.is_real_model:
        pytest.skip(
            "SKIPPED: Real LLM model weights not found on disk. "
            "Model 'Qwen2.5-0.5B-Instruct' GGUF or PyTorch checkpoint must be present "
            "to run genuine hardware generation tests."
        )
    return generator


# ==============================================================================
# NLI Genuine Model Evaluation Tests
# ==============================================================================

def test_live_nli_clearly_supported_claim():
    """Evaluate NLI model on a clearly supported factual claim."""
    runner = get_real_nli_runner()
    premise = "The Eiffel Tower is a wrought-iron lattice tower located on the Champ de Mars in Paris, France."
    hypothesis = "The Eiffel Tower is located in Paris, France."

    result = runner.predict(premise=premise, hypothesis=hypothesis)

    assert result["is_real_model"] is True
    assert result["inference_mode"] in ("onnx", "pytorch")
    assert result["status"] == "Supported"
    assert result["confidence"] >= 0.65
    assert result["scores"]["supported"] > result["scores"]["contradicted"]


def test_live_nli_clearly_contradicted_claim():
    """Evaluate NLI model on a clearly contradicted factual claim."""
    runner = get_real_nli_runner()
    premise = "The human heart has four chambers: two atria and two ventricles."
    hypothesis = "The human heart has only two chambers."

    result = runner.predict(premise=premise, hypothesis=hypothesis)

    assert result["is_real_model"] is True
    assert result["status"] == "Contradicted"
    assert result["confidence"] >= 0.65
    assert result["scores"]["contradicted"] > result["scores"]["supported"]


def test_live_nli_unverified_unrelated_evidence():
    """Evaluate NLI model on an unverified claim where evidence is unrelated."""
    runner = get_real_nli_runner()
    premise = "Jupiter is the largest planet in our solar system, with a mass greater than all other planets combined."
    hypothesis = "The Python programming language was created by Guido van Rossum in 1991."

    result = runner.predict(premise=premise, hypothesis=hypothesis)

    assert result["is_real_model"] is True
    assert result["status"] == "Unverified"


def test_live_nli_paraphrase_and_word_order():
    """Evaluate NLI model invariance to syntactic paraphrasing and word order changes."""
    runner = get_real_nli_runner()
    premise = "Water boils at 100 degrees Celsius under standard atmospheric pressure conditions."
    hypothesis = "Under standard atmospheric pressure, 100 degrees Celsius is the boiling point of water."

    result = runner.predict(premise=premise, hypothesis=hypothesis)

    assert result["is_real_model"] is True
    assert result["status"] == "Supported"
    assert result["confidence"] >= 0.65


def test_live_nli_out_of_domain_claim():
    """Evaluate NLI model robustness on specialized out-of-domain quantum mechanics claims."""
    runner = get_real_nli_runner()
    premise = (
        "Quantum entanglement occurs when pairs or groups of particles interact such that "
        "the quantum state of each particle cannot be described independently of the state of the others."
    )
    hypothesis = "Entangled particles possess completely independent quantum states regardless of spatial distance."

    result = runner.predict(premise=premise, hypothesis=hypothesis)

    assert result["is_real_model"] is True
    # Should detect contradiction or fall back to conservative Unverified
    assert result["status"] in ("Contradicted", "Unverified")


# ==============================================================================
# LLM Genuine Model Generation Tests
# ==============================================================================

def test_live_llm_grounded_correction_with_evidence():
    """Evaluate LLM correction quality when direct contradictory evidence is provided."""
    generator = get_real_llm_generator()
    claim = "The human heart has two chambers."
    evidence = "The human heart consists of four chambers: two upper atria and two lower ventricles."

    result = generator.generate_correction(claim=claim, evidence=evidence)

    assert result["is_real_model"] is True
    assert result["inference_mode"] in ("gguf_llama_cpp", "pytorch_transformers")
    assert result["abstain"] is False
    assert result["corrected_text"] != ""
    assert result["corrected_text"].strip().upper() != "NONE"
    assert "four" in result["corrected_text"].lower()


def test_live_llm_abstention_when_evidence_insufficient():
    """Evaluate LLM abstention (returning NONE) when evidence is unrelated or insufficient."""
    generator = get_real_llm_generator()
    claim = "The Apollo 11 mission was commanded by Neil Armstrong."
    evidence = "The Mariana Trench is located in the western Pacific Ocean and is the deepest oceanic trench on Earth."

    result = generator.generate_correction(claim=claim, evidence=evidence)

    assert result["is_real_model"] is True
    # Generator must abstain rather than hallucinate
    assert result["abstain"] is True or result["corrected_text"] == "NONE"


def test_live_llm_malformed_and_empty_inputs():
    """Evaluate LLM generator handling of empty or malformed prompts."""
    generator = get_real_llm_generator()

    # Empty claim
    res1 = generator.generate_correction(claim="", evidence="Valid evidence text.")
    assert res1["abstain"] is True or res1["corrected_text"] == "NONE"

    # Empty evidence
    res2 = generator.generate_correction(claim="Valid claim text.", evidence="")
    assert res2["abstain"] is True or res2["corrected_text"] == "NONE"

    # Both empty
    res3 = generator.generate_correction(claim="", evidence="")
    assert res3["abstain"] is True or res3["corrected_text"] == "NONE"


def test_live_llm_latency_and_bounded_execution():
    """Evaluate LLM generation latency bound on CPU hardware."""
    generator = get_real_llm_generator()
    claim = "Mars is the third planet from the Sun."
    evidence = "Mars is the fourth planet from the Sun, orbiting after Mercury, Venus, and Earth."

    result = generator.generate_correction(claim=claim, evidence=evidence)

    assert result["is_real_model"] is True
    assert "latency_ms" in result
    # On CPU, a 0.5B model generating ~20 tokens should finish well under 10 seconds
    assert result["latency_ms"] < 10000
