"""Unit tests for the AWS EC2 NLI and LLM inference microservice clients.

Validates:
1. Correct NLI endpoint and payload construction.
2. Correct Qwen endpoint and payload construction.
3. X-API-Key header injection without logging secrets.
4. Environment-variable configuration and missing-key behavior.
5. Trusted certificate verification and custom CA bundle support.
6. HTTP 401/403 responses.
7. Upstream 5xx errors.
8. Connection failures and read timeouts.
9. Malformed upstream responses.
10. Successful NLI verification and correction.
11. Existing API contract and regression tests.
12. Safe handling of unavailable inference services.
"""
import logging
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import requests

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from config import (
    build_endpoint_url,
    validate_inference_config,
)
from services.inference_client import (
    BaseInferenceClient,
    InferenceAuthError,
    InferenceClientError,
    InferenceConfigError,
    InferenceConnectionError,
    InferenceResponseError,
    InferenceServerError,
    InferenceTimeoutError,
    InferenceTLSError,
    LLMCorrectionClient,
    NLIClient,
    get_llm_client,
    get_nli_client,
    reset_clients,
)
from services.orchestrator import (
    build_corrected_paragraph,
    suggest_correction_remote,
    validate_correction_remote,
    verify_claim_remote,
)


@pytest.fixture(autouse=True)
def clean_client_singletons():
    """Reset singletons before and after each test."""
    reset_clients()
    yield
    reset_clients()


# ==============================================================================
# 1. Correct NLI Endpoint and Payload Construction
# ==============================================================================

def test_nli_endpoint_and_payload_construction():
    mock_session = MagicMock(spec=requests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "Supported",
        "confidence": 0.95,
        "scores": {"supported": 0.95, "contradicted": 0.02, "unverified": 0.03},
        "model": "cross-encoder/nli-MiniLM2-L6-H768",
        "is_real_model": True,
    }
    mock_session.request.return_value = mock_response

    client = NLIClient(
        base_url="https://13.205.17.228",
        api_key="test-key",
        session=mock_session,
    )

    # Test single verify
    result = client.verify(claim="The Earth revolves around the Sun.", evidence="Earth orbits the Sun annually.")

    assert mock_session.request.called
    args, kwargs = mock_session.request.call_args
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "https://13.205.17.228/nli/verify"
    assert kwargs["json"] == {
        "claim": "The Earth revolves around the Sun.",
        "evidence": "Earth orbits the Sun annually.",
    }
    assert result["status"] == "Supported"
    assert result["confidence"] == 0.95

    # Test verify-batch
    mock_response.json.return_value = {
        "results": [
            {"status": "Supported", "confidence": 0.95},
            {"status": "Contradicted", "confidence": 0.91},
        ]
    }
    pairs = [
        {"claim": "Claim 1", "evidence": "Evidence 1"},
        {"claim": "Claim 2", "evidence": "Evidence 2"},
    ]
    batch_result = client.verify_batch(pairs)
    assert batch_result["count"] == 2
    args, kwargs = mock_session.request.call_args
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "https://13.205.17.228/nli/verify-batch"
    assert kwargs["json"] == {"pairs": pairs}


# ==============================================================================
# 2. Correct Qwen Endpoint and Payload Construction
# ==============================================================================

def test_qwen_endpoint_and_payload_construction():
    mock_session = MagicMock(spec=requests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "correction": "The capital of Australia is Canberra.",
        "tokens_generated": 8,
        "abstain": False,
        "model": "Qwen2.5-0.5B-Instruct",
    }
    mock_session.request.return_value = mock_response

    client = LLMCorrectionClient(
        base_url="https://13.205.17.228",
        api_key="test-key",
        session=mock_session,
    )

    result = client.correct(
        claim="The capital of Australia is Sydney.",
        evidence="Canberra is the capital city of Australia.",
    )

    assert mock_session.request.called
    args, kwargs = mock_session.request.call_args
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "https://13.205.17.228/llm/correct"
    assert kwargs["json"] == {
        "claim": "The capital of Australia is Sydney.",
        "evidence": "Canberra is the capital city of Australia.",
    }
    assert result["correction"] == "The capital of Australia is Canberra."
    assert result["abstain"] is False


# ==============================================================================
# 3. X-API-Key Header Injection without Logging the Secret
# ==============================================================================

def test_api_key_header_injection_and_no_credential_logging(caplog):
    secret_key = "super-secret-production-token-998877"
    mock_session = MagicMock(spec=requests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_session.request.return_value = mock_response

    with caplog.at_level(logging.DEBUG):
        client = BaseInferenceClient(
            base_url="https://13.205.17.228",
            api_key=secret_key,
            session=mock_session,
        )
        client._request(method="GET", path="/health")

    args, kwargs = mock_session.request.call_args
    assert "X-API-Key" in kwargs["headers"]
    assert kwargs["headers"]["X-API-Key"] == secret_key

    # CRITICAL: Verify secret token is NOT leaked in any log records
    for record in caplog.records:
        assert secret_key not in record.message


# ==============================================================================
# 4. Environment-Variable Configuration and Missing-Key Behavior
# ==============================================================================

def test_environment_configuration_and_missing_key_behavior():
    # URL normalization
    assert build_endpoint_url("https://13.205.17.228/", "/nli/verify") == "https://13.205.17.228/nli/verify"
    assert build_endpoint_url("https://13.205.17.228", "nli/verify") == "https://13.205.17.228/nli/verify"

    # Missing API key initialization
    client = BaseInferenceClient(base_url="https://13.205.17.228", api_key="")
    headers = client._get_headers()
    assert "X-API-Key" not in headers

    # Validation diagnostics
    with patch.dict(os.environ, {"INFERENCE_API_KEY": ""}, clear=False):
        status = validate_inference_config()
        assert status["has_api_key"] is False
        assert any("INFERENCE_API_KEY is not set" in w for w in status["warnings"])


# ==============================================================================
# 5. Trusted Certificate Verification and Custom CA Bundle Support
# ==============================================================================

def test_trusted_certificate_verification_and_custom_ca_bundle():
    # Default without CA bundle must enforce strict system trust (tls_verify=True, NEVER False)
    client_default = BaseInferenceClient(base_url="https://13.205.17.228", ca_bundle_path="")
    assert client_default.tls_verify is True

    # Custom CA bundle that exists
    with tempfile.NamedTemporaryFile(suffix=".crt", delete=False) as tmp_ca:
        tmp_ca.write(b"-----BEGIN CERTIFICATE-----\nMIIB...\n-----END CERTIFICATE-----\n")
        tmp_ca_path = tmp_ca.name

    try:
        client_custom = BaseInferenceClient(base_url="https://13.205.17.228", ca_bundle_path=tmp_ca_path)
        assert client_custom.tls_verify == tmp_ca_path
    finally:
        if os.path.exists(tmp_ca_path):
            os.remove(tmp_ca_path)

    # Custom CA bundle that does NOT exist must fail fast
    non_existent_path = "/path/to/nonexistent/ca-bundle.crt"
    with pytest.raises(InferenceConfigError) as exc_info:
        BaseInferenceClient(base_url="https://13.205.17.228", ca_bundle_path=non_existent_path)
    assert "does not exist" in str(exc_info.value)


# ==============================================================================
# 6. HTTP 401/403 Responses
# ==============================================================================

def test_http_401_403_responses():
    mock_session = MagicMock(spec=requests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_session.request.return_value = mock_response

    client = NLIClient(base_url="https://13.205.17.228", session=mock_session)
    with pytest.raises(InferenceAuthError) as exc_info:
        client.verify(claim="Test claim", evidence="Test evidence")
    assert "authentication failed" in str(exc_info.value).lower()

    # Orchestrator handling of 401
    with patch("services.orchestrator.get_nli_client", return_value=client):
        result = verify_claim_remote("Test claim", "Test evidence that has more than 30 characters.")
        assert result["status"] == "Unverified"
        assert result["error"] == "upstream_unauthorized"


# ==============================================================================
# 7. Upstream 5xx Errors
# ==============================================================================

def test_upstream_5xx_errors():
    mock_session = MagicMock(spec=requests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 502
    mock_session.request.return_value = mock_response

    client = NLIClient(base_url="https://13.205.17.228", session=mock_session)
    with pytest.raises(InferenceServerError) as exc_info:
        client.verify(claim="Test claim", evidence="Test evidence")
    assert "502" in str(exc_info.value)

    # Orchestrator handling of 502
    with patch("services.orchestrator.get_nli_client", return_value=client):
        result = verify_claim_remote("Test claim", "Test evidence that has more than 30 characters.")
        assert result["status"] == "Unverified"
        assert result["error"] == "upstream_server_error"


# ==============================================================================
# 8. Connection Failures and Read Timeouts
# ==============================================================================

def test_connection_failures_and_read_timeouts():
    mock_session = MagicMock(spec=requests.Session)
    mock_session.request.side_effect = requests.exceptions.ConnectTimeout("Connection timed out")

    client = NLIClient(base_url="https://13.205.17.228", session=mock_session)
    with pytest.raises(InferenceTimeoutError):
        client.verify(claim="Test claim", evidence="Test evidence")

    mock_session.request.side_effect = requests.exceptions.ConnectionError("Network down")
    with pytest.raises(InferenceConnectionError):
        client.verify(claim="Test claim", evidence="Test evidence")


# ==============================================================================
# 9. Malformed Upstream Responses
# ==============================================================================

def test_malformed_upstream_responses():
    mock_session = MagicMock(spec=requests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Malformed JSON payload")
    mock_session.request.return_value = mock_response

    client = NLIClient(base_url="https://13.205.17.228", session=mock_session)
    with pytest.raises(InferenceResponseError):
        client.verify(claim="Test claim", evidence="Test evidence")


# ==============================================================================
# 10. Successful NLI Verification and Correction
# ==============================================================================

def test_successful_nli_verification_and_correction():
    mock_nli_session = MagicMock(spec=requests.Session)
    mock_nli_resp = MagicMock()
    mock_nli_resp.status_code = 200
    mock_nli_resp.json.return_value = {
        "status": "Contradicted",
        "confidence": 0.92,
        "scores": {"contradicted": 0.92, "supported": 0.03, "unverified": 0.05},
        "model": "cross-encoder/nli-MiniLM2-L6-H768",
        "is_real_model": True,
    }
    mock_nli_session.request.return_value = mock_nli_resp

    mock_llm_session = MagicMock(spec=requests.Session)
    mock_llm_resp = MagicMock()
    mock_llm_resp.status_code = 200
    mock_llm_resp.json.return_value = {
        "correction": "The human heart has four chambers.",
        "tokens_generated": 7,
        "abstain": False,
        "model": "Qwen2.5-0.5B-Instruct",
    }
    mock_llm_session.request.return_value = mock_llm_resp

    nli_client = NLIClient(base_url="https://13.205.17.228", session=mock_nli_session)
    llm_client = LLMCorrectionClient(base_url="https://13.205.17.228", session=mock_llm_session)

    with patch("services.orchestrator.get_nli_client", return_value=nli_client), \
         patch("services.orchestrator.get_llm_client", return_value=llm_client):

        verify_res = verify_claim_remote(
            claim="The human heart has two chambers.",
            evidence="The human heart has four chambers: two atria and two ventricles.",
        )
        assert verify_res["status"] == "Contradicted"
        assert verify_res["confidence"] == 0.92
        assert "contradicts" in verify_res["explanation"]

        correction_text = suggest_correction_remote(
            claim="The human heart has two chambers.",
            evidence="The human heart has four chambers: two atria and two ventricles.",
        )
        assert correction_text == "The human heart has four chambers."


# ==============================================================================
# 11. Existing API Contract and Regression Tests
# ==============================================================================

def test_api_contract_and_correction_validation():
    # Empty claim
    res_empty = verify_claim_remote("", "Some long evidence that passes the length threshold.")
    assert res_empty["status"] == "Unverified"
    assert res_empty["error"] == "empty_claim"

    # Short evidence
    res_short = verify_claim_remote("Valid claim", "Too short.")
    assert res_short["status"] == "Unverified"
    assert res_short["error"] == "insufficient_evidence"

    # Correction identical to claim must be rejected
    assert validate_correction_remote("The Earth revolves around the Sun", "The Earth revolves around the Sun", "Evidence") is False

    # Paragraph construction
    results = [
        {"status": "Supported", "sentence": "Paris is the capital of France."},
        {
            "status": "Contradicted",
            "sentence": "The Sun revolves around the Earth.",
            "correction": "The Earth revolves around the Sun.",
            "correction_validated": True,
        },
        {"status": "Unverified", "sentence": "Some unverified sentence."},
    ]
    paragraph = build_corrected_paragraph(results)
    assert paragraph == "Paris is the capital of France. The Earth revolves around the Sun. Some unverified sentence."


# ==============================================================================
# 12. Safe Handling of Unavailable Inference Services (TLS Error)
# ==============================================================================

def test_safe_handling_of_unavailable_services_tls_error():
    mock_session = MagicMock(spec=requests.Session)
    mock_session.request.side_effect = requests.exceptions.SSLError("Self-signed certificate verification failed")

    client = NLIClient(base_url="https://13.205.17.228", session=mock_session)

    # Client raises InferenceTLSError
    with pytest.raises(InferenceTLSError):
        client.verify("Test claim", "Test evidence")

    # Orchestrator catches and returns safe Unverified with diagnostic error
    with patch("services.orchestrator.get_nli_client", return_value=client):
        res = verify_claim_remote("Test claim", "Test evidence that has more than 30 characters.")
        assert res["status"] == "Unverified"
        assert res["error"] == "tls_verification_failed"
        assert "trusted CA bundle" in res["explanation"]

    # Health check handles TLS failure safely without hanging
    health_res = client.check_health()
    assert health_res["available"] is False
    assert health_res["error"] == "tls_verification_failed"
