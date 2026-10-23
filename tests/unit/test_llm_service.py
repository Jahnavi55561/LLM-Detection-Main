"""Unit tests for the LLM correction generator, prompt formulation, and cleaning."""
import sys
import os
import pytest

LLM_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "model-services", "llm-correction"))
if LLM_PATH not in sys.path:
    sys.path.insert(0, LLM_PATH)

from generator import LLMCorrectionGenerator

def test_llm_generator_initialization():
    gen = LLMCorrectionGenerator()
    assert gen.initialize() is True
    status = gen.status()
    assert status["loaded"] is True
    assert status["max_tokens"] == 64
    assert status["is_real_model_ready"] is False
    assert status["inference_mode"] == "offline_calibrated_mock"
    assert status["status"] == "degraded_fallback"

def test_llm_generator_prompt_format():
    gen = LLMCorrectionGenerator()
    claim = "The Moon produces visible light."
    evidence = "The Moon reflects sunlight."
    prompt = gen._build_prompt(claim, evidence)

    assert "CLAIM:" in prompt
    assert "EVIDENCE:" in prompt
    assert "ONLY the facts in the evidence" in prompt
    assert claim in prompt
    assert evidence in prompt

def test_llm_clean_output_strips_preamble():
    gen = LLMCorrectionGenerator()
    raw_1 = 'Here is the corrected sentence: Canberra is the capital of Australia.'
    assert gen._clean_output(raw_1) == 'Canberra is the capital of Australia.'

    raw_2 = 'Sure, here is the correction: "The Earth revolves around the Sun."'
    assert gen._clean_output(raw_2) == 'The Earth revolves around the Sun.'

    raw_3 = 'NONE'
    assert gen._clean_output(raw_3) == ''

    raw_4 = 'UNKNOWN.'
    assert gen._clean_output(raw_4) == ''

def test_llm_generation_with_evidence():
    gen = LLMCorrectionGenerator()
    gen.initialize()
    claim = "The capital of Australia is Sydney."
    evidence = "Canberra is the capital city of Australia."
    result = gen.generate_correction(claim, evidence)

    assert "correction" in result
    assert len(result["correction"]) > 0
    assert "Australia" in result["correction"] or "Canberra" in result["correction"]
