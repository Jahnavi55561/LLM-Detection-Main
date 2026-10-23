"""Integration tests for the Flask Backend API endpoints and workflows."""
from unittest.mock import patch

def test_api_health_endpoint(backend_client):
    response = backend_client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["service"] == "backend-gateway"
    assert "nli_service" in data
    assert "llm_service" in data

def test_analyze_empty_payload(backend_client):
    response = backend_client.post("/api/analyze", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data

def test_analyze_oversized_payload(backend_client):
    large_text = "A" * 10005
    response = backend_client.post("/api/analyze", json={"text": large_text})
    assert response.status_code == 413
    data = response.get_json()
    assert "error" in data

def test_analyze_too_many_sentences(backend_client):
    text = " ".join([f"Sentence number {i} is here." for i in range(35)])
    response = backend_client.post("/api/analyze", json={"text": text})
    assert response.status_code == 400
    data = response.get_json()
    assert "Maximum 30 sentences" in data["error"]

@patch("backend.app.verify_claim_remote")
@patch("backend.app.suggest_correction_remote")
@patch("backend.app.validate_correction_remote")
def test_analyze_full_workflow(mock_validate, mock_suggest, mock_verify, backend_client):
    # Configure mock responses for remote microservices
    def fake_verify(claim, evidence):
        if "revolves around the sun" in claim.lower():
            return {"status": "Supported", "confidence": 0.95, "explanation": "Evidence supports claim."}
        if "sydney" in claim.lower():
            return {"status": "Contradicted", "confidence": 0.92, "explanation": "Evidence contradicts claim."}
        return {"status": "Unverified", "confidence": 0.0, "explanation": "Unverified."}

    mock_verify.side_effect = fake_verify
    mock_suggest.return_value = "Canberra is the capital of Australia."
    mock_validate.return_value = True

    text = "The Earth revolves around the Sun. The capital of Australia is Sydney."
    response = backend_client.post("/api/analyze", json={"text": text})

    assert response.status_code == 200
    data = response.get_json()

    assert data["total_sentences"] == 2
    assert data["supported_count"] == 1
    assert data["contradicted_count"] == 1
    assert data["unverified_count"] == 0

    assert len(data["results"]) == 2
    assert data["results"][0]["status"] == "Supported"
    assert data["results"][1]["status"] == "Contradicted"
    assert data["results"][1]["correction"] == "Canberra is the capital of Australia."
    assert data["results"][1]["correction_validated"] is True
    assert "Canberra is the capital of Australia." in data["corrected_paragraph"]

def test_chat_endpoint(backend_client):
    response = backend_client.post("/api/chat", json={"message": "The Earth revolves around the Sun."})
    assert response.status_code == 200
    data = response.get_json()
    assert "status" in data
    assert "reply" in data

def test_chat_empty_message(backend_client):
    response = backend_client.post("/api/chat", json={"message": ""})
    assert response.status_code == 400

def test_history_workflow(backend_client):
    # Check history endpoint
    resp = backend_client.get("/api/history")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "history" in data

    # Clear history
    clear_resp = backend_client.post("/api/history/clear")
    assert clear_resp.status_code == 200
    assert clear_resp.get_json()["ok"] is True

def test_frontend_static_serving(backend_client):
    resp_index = backend_client.get("/")
    assert resp_index.status_code == 200
    assert b"LLM Hallucination Detector" in resp_index.data

    resp_css = backend_client.get("/css/style.css")
    assert resp_css.status_code == 200

    resp_js = backend_client.get("/js/script.js")
    assert resp_js.status_code == 200
