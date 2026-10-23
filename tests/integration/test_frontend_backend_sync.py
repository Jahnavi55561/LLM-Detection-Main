"""Integration tests verifying frontend and backend schema synchronization and failure-state handling."""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.app import app as backend_app
from backend.services.inference_client import (
    InferenceServerError,
    InferenceTimeoutError,
    InferenceTLSError,
    LLMCorrectionClient,
    NLIClient,
    reset_clients,
)


@pytest.fixture
def client():
    backend_app.config["TESTING"] = True
    with backend_app.test_client() as test_client:
        yield test_client
    reset_clients()


# ==============================================================================
# 1. Static Frontend and Asset Serving
# ==============================================================================

def test_static_frontend_and_assets_serving(client):
    # Root index.html
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="input-text"' in html
    assert '<textarea' in html
    assert 'id="analyze-btn"' in html
    assert 'id="sidebar-status"' in html
    assert 'id="result-list"' in html
    assert 'id="system-status-text"' in html
    assert '<meta name="backend-api-url"' in html
    assert 'content="https://llm-detection-api.onrender.com"' in html

    # CSS serving
    resp_css = client.get("/css/style.css")
    assert resp_css.status_code == 200
    css = resp_css.get_data(as_text=True)
    assert ".status-dot" in css
    assert ".status-dot.ready" in css
    assert ".status-dot.warning" in css
    assert ".status-dot.error" in css

    # JS serving
    resp_js = client.get("/js/script.js")
    assert resp_js.status_code == 200
    js = resp_js.get_data(as_text=True)
    assert "API_BASE_URL" in js
    assert "checkBackendHealth" in js
    assert "renderResult" in js

    # Legacy static alias serving
    resp_static_css = client.get("/static/style.css")
    assert resp_static_css.status_code == 200

    resp_static_js = client.get("/static/script.js")
    assert resp_static_js.status_code == 200
    static_js = resp_static_js.get_data(as_text=True)
    assert "API_BASE_URL" in static_js
    assert "backend-api-url" in static_js


# ==============================================================================
# 2. Analyze Request / Response Schema Compatibility
# ==============================================================================

@patch("backend.app.retrieve_evidence")
@patch("backend.app.verify_claim_remote")
@patch("backend.app.suggest_correction_remote")
@patch("backend.app.validate_correction_remote")
def test_analyze_request_response_schema_compatibility(mock_validate, mock_suggest, mock_verify, mock_retrieve, client):
    mock_retrieve.return_value = {
        "evidence": "Earth orbits the Sun once annually. Canberra is the capital of Australia.",
        "source": "Wikipedia",
        "source_url": "https://en.wikipedia.org/wiki/Earth",
    }

    def fake_verify(claim, evidence):
        if "revolves around the sun" in claim.lower():
            return {
                "status": "Supported",
                "confidence": 0.96,
                "scores": {"supported": 0.96, "contradicted": 0.02, "unverified": 0.02},
                "model": "cross-encoder/nli-MiniLM2-L6-H768",
                "inference_mode": "remote_ec2",
                "is_real_model": True,
                "latency_ms": 24.0,
                "error": None,
            }
        if "sydney" in claim.lower():
            return {
                "status": "Contradicted",
                "confidence": 0.93,
                "scores": {"supported": 0.02, "contradicted": 0.93, "unverified": 0.05},
                "model": "cross-encoder/nli-MiniLM2-L6-H768",
                "inference_mode": "remote_ec2",
                "is_real_model": True,
                "latency_ms": 25.0,
                "error": None,
            }
        return {"status": "Unverified", "confidence": 0.0, "scores": {}, "model": "nli", "is_real_model": True}

    mock_verify.side_effect = fake_verify
    mock_suggest.return_value = "The capital of Australia is Canberra."
    mock_validate.return_value = True

    # Frontend payload structure: JSON object with "text" field
    frontend_payload = {
        "text": "The Earth revolves around the Sun. The capital of Australia is Sydney."
    }
    resp = client.post("/api/analyze", json=frontend_payload)
    assert resp.status_code == 200
    data = resp.get_json()

    # Verify top-level contract matching frontend expectation
    assert "results" in data
    assert "counts" in data
    assert "corrected_paragraph" in data
    assert data["total_sentences"] == 2
    assert data["supported_count"] == 1
    assert data["contradicted_count"] == 1
    assert data["unverified_count"] == 0

    # Verify each result card item schema parsed by renderResult() in frontend
    res0 = data["results"][0]
    assert res0["id"] == 1
    assert res0["sentence"] == "The Earth revolves around the Sun."
    assert res0["status"] == "Supported"
    assert res0["confidence"] == 0.96
    assert "supports" in res0["explanation"].lower()
    assert "evidence" in res0
    assert "source" in res0
    assert "source_url" in res0

    res1 = data["results"][1]
    assert res1["id"] == 2
    assert res1["sentence"] == "The capital of Australia is Sydney."
    assert res1["status"] == "Contradicted"
    assert res1["confidence"] == 0.93
    assert res1["correction"] == "The capital of Australia is Canberra."
    assert res1["correction_validated"] is True

    # Verify paragraph construction
    assert "Canberra" in data["corrected_paragraph"]


# ==============================================================================
# 3. Chat Endpoint Request / Response Schema Compatibility
# ==============================================================================

@patch("backend.services.orchestrator.get_nli_client")
def test_chat_endpoint_schema_compatibility(mock_get_nli, client):
    mock_nli = MagicMock(spec=NLIClient)
    mock_nli.verify.return_value = {
        "status": "Supported",
        "confidence": 0.94,
        "scores": {"supported": 0.94, "contradicted": 0.02, "unverified": 0.04},
        "model": "cross-encoder/nli-MiniLM2-L6-H768",
        "is_real_model": True,
        "latency_ms": 22.0,
        "error": None,
    }
    mock_get_nli.return_value = mock_nli

    # Frontend chat assistant sends {"message": "..."}
    resp = client.post("/api/chat", json={"message": "Does the Earth revolve around the Sun?"})
    assert resp.status_code == 200
    data = resp.get_json()

    # Verify fields parsed by frontend chat assistant
    assert data["status"] == "Supported"
    assert data["confidence"] == 0.94
    assert "reply" in data
    assert "evidence" in data
    assert "source" in data
    assert "source_url" in data

    # Verify tolerance for alternate keys ("question" and "text")
    resp_q = client.post("/api/chat", json={"question": "Does the Earth revolve around the Sun?"})
    assert resp_q.status_code == 200
    assert resp_q.get_json()["status"] == "Supported"

    # Empty chat prompt rejected with 400
    resp_empty = client.post("/api/chat", json={"message": "   "})
    assert resp_empty.status_code == 400


# ==============================================================================
# 4. Health Endpoint Schema & State Distinction (Phase 5)
# ==============================================================================

def test_health_state_distinction_both_operational(client):
    """State A: Both EC2 models are fully operational with real weights."""
    mock_nli = MagicMock(spec=NLIClient)
    mock_llm = MagicMock(spec=LLMCorrectionClient)
    mock_nli.check_health.return_value = {
        "available": True,
        "status": "healthy_real_model",
        "is_real_model_ready": True,
        "inference_mode": "remote_ec2",
        "model_name": "cross-encoder/nli-MiniLM2-L6-H768",
    }
    mock_llm.check_health.return_value = {
        "available": True,
        "status": "healthy_real_model",
        "is_real_model_ready": True,
        "inference_mode": "remote_ec2",
        "model_name": "Qwen2.5-0.5B-Instruct",
    }

    with patch("backend.app.get_nli_client", return_value=mock_nli), \
         patch("backend.app.get_llm_client", return_value=mock_llm):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["nli_service"]["available"] is True
        assert data["nli_service"]["is_real_model_ready"] is True
        assert data["llm_service"]["available"] is True
        assert data["llm_service"]["is_real_model_ready"] is True


def test_health_state_distinction_nli_offline(client):
    """State B: NLI unavailable, LLM available."""
    mock_nli = MagicMock(spec=NLIClient)
    mock_llm = MagicMock(spec=LLMCorrectionClient)
    mock_nli.check_health.return_value = {
        "available": False,
        "error": "upstream_connection_error",
        "status": "unavailable",
    }
    mock_llm.check_health.return_value = {
        "available": True,
        "status": "healthy_real_model",
        "is_real_model_ready": True,
        "model_name": "Qwen2.5-0.5B-Instruct",
    }

    with patch("backend.app.get_nli_client", return_value=mock_nli), \
         patch("backend.app.get_llm_client", return_value=mock_llm):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True  # Render backend is healthy
        assert data["nli_service"]["available"] is False
        assert data["nli_service"]["error"] == "upstream_connection_error"
        assert data["llm_service"]["available"] is True


def test_health_state_distinction_tls_error(client):
    """State C: Self-signed certificate TLS error (active EC2 prerequisite)."""
    mock_nli = MagicMock(spec=NLIClient)
    mock_llm = MagicMock(spec=LLMCorrectionClient)
    mock_nli.check_health.return_value = {
        "available": False,
        "error": "tls_verification_failed",
        "status": "unavailable",
    }
    mock_llm.check_health.return_value = {
        "available": False,
        "error": "tls_verification_failed",
        "status": "unavailable",
    }

    with patch("backend.app.get_nli_client", return_value=mock_nli), \
         patch("backend.app.get_llm_client", return_value=mock_llm):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["nli_service"]["available"] is False
        assert data["nli_service"]["error"] == "tls_verification_failed"
        assert data["llm_service"]["available"] is False
        assert data["llm_service"]["error"] == "tls_verification_failed"


def test_health_endpoint_no_secrets_leaked(client):
    """Ensure no API keys, internal paths, or credentials leak in health response."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    raw_text = resp.get_data(as_text=True)
    assert "INFERENCE_API_KEY" not in raw_text
    assert "api_key" not in raw_text
    assert "BEGIN CERTIFICATE" not in raw_text


# ==============================================================================
# 5. Unavailable Upstream Never Produces Successful Verdicts
# ==============================================================================

@patch("backend.app.retrieve_evidence", return_value={"evidence": "Water is a chemical compound consisting of two hydrogen atoms and one oxygen atom.", "source": "Chemistry KB", "source_url": ""})
@patch("backend.app.verify_claim_remote")
def test_unavailable_upstream_never_produces_supported_verdict(mock_verify, mock_retrieve, client):
    mock_verify.return_value = {
        "status": "Unverified",
        "confidence": 0.0,
        "explanation": "Inference TLS certificate verification failed. A trusted CA bundle is required.",
        "error": "tls_verification_failed",
        "is_real_model": False,
    }

    resp = client.post("/api/analyze", json={"text": "Water boils at 100 degrees Celsius."})
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["supported_count"] == 0
    assert data["unverified_count"] == 1
    result = data["results"][0]
    assert result["status"] == "Unverified"
    assert result["error"] == "tls_verification_failed"
    assert "TLS certificate verification failed" in result["explanation"]


# ==============================================================================
# 6. Correction Failure Never Fabricates Correction
# ==============================================================================

@patch("backend.app.retrieve_evidence", return_value={"evidence": "Humans have two lungs located inside the thoracic cavity.", "source": "Biology KB", "source_url": ""})
@patch("backend.app.verify_claim_remote")
@patch("backend.app.suggest_correction_remote", return_value="")
@patch("backend.app.validate_correction_remote", return_value=False)
def test_correction_failure_never_fabricates_correction(mock_validate, mock_suggest, mock_verify, mock_retrieve, client):
    mock_verify.return_value = {
        "status": "Contradicted",
        "confidence": 0.90,
        "explanation": "Evidence contradicts claim.",
        "evidence": "Humans have two lungs.",
        "source": "Biology KB",
        "is_real_model": True,
        "error": None,
    }

    resp = client.post("/api/analyze", json={"text": "Humans have three lungs."})
    assert resp.status_code == 200
    data = resp.get_json()

    result = data["results"][0]
    assert result["status"] == "Contradicted"
    assert result["correction"] == ""
    assert result["correction_validated"] is False
    assert "No validated corrections" in data["corrected_paragraph"] or data["corrected_paragraph"] == "Humans have three lungs."


# ==============================================================================
# 7. History and Clear Workflow
# ==============================================================================

def test_history_and_clear_workflow(client):
    # Clear initial history
    client.post("/api/history/clear")

    # Verify history starts empty
    resp_empty = client.get("/api/history")
    assert resp_empty.status_code == 200
    assert resp_empty.get_json()["history"] == []

    # Perform analyze request
    client.post("/api/analyze", json={"text": "The Earth revolves around the Sun."})

    # History now contains item with schema matching renderHistoryItem()
    resp_hist = client.get("/api/history")
    assert resp_hist.status_code == 200
    history = resp_hist.get_json()["history"]
    assert len(history) == 1
    item = history[0]
    assert "preview" in item
    assert "counts" in item
    assert "timestamp" in item
    assert item["total_sentences"] == 1

    # Clear history
    resp_clear = client.post("/api/history/clear")
    assert resp_clear.status_code == 200
    assert resp_clear.get_json()["ok"] is True

    # History is empty again
    resp_empty_after = client.get("/api/history")
    assert resp_empty_after.get_json()["history"] == []
