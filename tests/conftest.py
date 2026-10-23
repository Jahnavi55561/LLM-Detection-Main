"""Pytest configuration and shared fixtures for unit and integration testing."""
import json
import os
import sys
import pytest

# Add project root and services to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

NLI_DIR = os.path.join(PROJECT_ROOT, "model-services", "nli-verification")
if NLI_DIR not in sys.path:
    sys.path.insert(0, NLI_DIR)

LLM_DIR = os.path.join(PROJECT_ROOT, "model-services", "llm-correction")
if LLM_DIR not in sys.path:
    sys.path.insert(0, LLM_DIR)

from backend.app import app as backend_app

@pytest.fixture
def backend_client():
    backend_app.config["TESTING"] = True
    with backend_app.test_client() as client:
        yield client

@pytest.fixture
def benchmark_data():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "benchmark_dataset.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)
