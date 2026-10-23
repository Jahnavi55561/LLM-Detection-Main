"""Unit tests for the NLI verification runner, label mapping, and calibration."""
import sys
import os
import pytest

# Ensure nli-verification service can be imported
NLI_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "model-services", "nli-verification"))
if NLI_PATH not in sys.path:
    sys.path.insert(0, NLI_PATH)

from model_runner import NLIModelRunner

def test_nli_runner_initialization():
    runner = NLIModelRunner(threshold=0.65, margin=0.10)
    assert runner.initialize() is True
    status = runner.status()
    assert status["loaded"] is True
    assert status["threshold"] == 0.65
    assert status["is_real_model_ready"] is False
    assert status["inference_mode"] == "offline_calibrated_mock"
    assert status["status"] == "degraded_fallback"

def test_nli_runner_predict_supported():
    runner = NLIModelRunner()
    runner.initialize()
    premise = "Earth orbits the Sun once approximately every 365.25 days."
    hypothesis = "The Earth revolves around the Sun."
    result = runner.predict(premise=premise, hypothesis=hypothesis)

    assert result["status"] == "Supported"
    assert result["confidence"] >= 0.65
    assert result["scores"]["supported"] > result["scores"]["contradicted"]

def test_nli_runner_predict_contradicted():
    runner = NLIModelRunner()
    runner.initialize()
    premise = "Earth orbits the Sun. The heliocentric model describes planets revolving around the central star."
    hypothesis = "The Sun revolves around the Earth."
    result = runner.predict(premise=premise, hypothesis=hypothesis)

    assert result["status"] == "Contradicted"
    assert result["confidence"] >= 0.65
    assert result["scores"]["contradicted"] > result["scores"]["supported"]

def test_nli_runner_predict_unverified():
    runner = NLIModelRunner()
    runner.initialize()
    premise = "Quantum computers operate using qubits rather than binary bits."
    hypothesis = "The capital of Australia is Sydney."
    result = runner.predict(premise=premise, hypothesis=hypothesis)

    assert result["status"] == "Unverified"
    assert "scores" in result

def test_nli_runner_empty_inputs():
    runner = NLIModelRunner()
    runner.initialize()
    result = runner.predict(premise="", hypothesis="Some claim.")
    assert result["status"] == "Unverified"
    assert result["confidence"] == 0.0
