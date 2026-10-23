"""Reusable HTTP clients for AWS EC2 NLI and LLM inference microservices.

Enforces:
- X-API-Key header injection without leaking credentials in logs.
- Strict TLS certificate verification with optional trusted CA bundle (NEVER verify=False).
- Bounded connect/read timeouts.
- Idempotency-conscious retry controls.
- Clean mapping of upstream responses into backend domain contracts.
"""
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from ..config import (
        INFERENCE_API_KEY,
        INFERENCE_CA_BUNDLE_PATH,
        INFERENCE_CONNECT_TIMEOUT,
        INFERENCE_MAX_RETRIES,
        INFERENCE_READ_TIMEOUT,
        LLM_CORRECT_PATH,
        LLM_HEALTH_PATH,
        LLM_SERVICE_BASE_URL,
        NLI_HEALTH_PATH,
        NLI_SERVICE_BASE_URL,
        NLI_VERIFY_BATCH_PATH,
        NLI_VERIFY_PATH,
        build_endpoint_url,
    )
except (ImportError, ValueError):
    from config import (
        INFERENCE_API_KEY,
        INFERENCE_CA_BUNDLE_PATH,
        INFERENCE_CONNECT_TIMEOUT,
        INFERENCE_MAX_RETRIES,
        INFERENCE_READ_TIMEOUT,
        LLM_CORRECT_PATH,
        LLM_HEALTH_PATH,
        LLM_SERVICE_BASE_URL,
        NLI_HEALTH_PATH,
        NLI_SERVICE_BASE_URL,
        NLI_VERIFY_BATCH_PATH,
        NLI_VERIFY_PATH,
        build_endpoint_url,
    )

logger = logging.getLogger("backend.inference_client")


# ==============================================================================
# Custom Exception Hierarchy
# ==============================================================================

class InferenceClientError(Exception):
    """Base exception for inference client failures."""
    def __init__(self, message: str, error_code: str = "inference_error"):
        super().__init__(message)
        self.error_code = error_code


class InferenceConfigError(InferenceClientError):
    """Configuration error (e.g. invalid CA bundle path or missing required settings)."""
    def __init__(self, message: str):
        super().__init__(message, error_code="configuration_error")


class InferenceTLSError(InferenceClientError):
    """TLS certificate verification failed (e.g. self-signed cert without CA bundle)."""
    def __init__(self, message: str):
        super().__init__(message, error_code="tls_verification_failed")


class InferenceAuthError(InferenceClientError):
    """Upstream authentication error (HTTP 401 or 403 - missing or invalid API key)."""
    def __init__(self, message: str):
        super().__init__(message, error_code="upstream_unauthorized")


class InferenceServerError(InferenceClientError):
    """Upstream 5xx server error."""
    def __init__(self, message: str):
        super().__init__(message, error_code="upstream_server_error")


class InferenceTimeoutError(InferenceClientError):
    """Connect or read timeout."""
    def __init__(self, message: str):
        super().__init__(message, error_code="upstream_timeout")


class InferenceConnectionError(InferenceClientError):
    """Network connection failure reaching upstream gateway."""
    def __init__(self, message: str):
        super().__init__(message, error_code="upstream_connection_error")


class InferenceResponseError(InferenceClientError):
    """Malformed or unexpected response payload from upstream."""
    def __init__(self, message: str):
        super().__init__(message, error_code="malformed_upstream_response")


# ==============================================================================
# Base Inference Client
# ==============================================================================

class BaseInferenceClient:
    """Base HTTP client with TLS verification, authentication, and bounded timeouts."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        ca_bundle_path: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = (api_key if api_key is not None else INFERENCE_API_KEY) or ""
        self.ca_bundle_path = (ca_bundle_path if ca_bundle_path is not None else INFERENCE_CA_BUNDLE_PATH) or ""
        self.connect_timeout = float(connect_timeout if connect_timeout is not None else INFERENCE_CONNECT_TIMEOUT)
        self.read_timeout = float(read_timeout if read_timeout is not None else INFERENCE_READ_TIMEOUT)
        self.max_retries = int(max_retries if max_retries is not None else INFERENCE_MAX_RETRIES)

        # Validate CA bundle if specified
        if self.ca_bundle_path:
            if not os.path.exists(self.ca_bundle_path):
                raise InferenceConfigError(
                    f"Configured INFERENCE_CA_BUNDLE_PATH does not exist: {self.ca_bundle_path}"
                )
            self.tls_verify = self.ca_bundle_path
        else:
            # Standard system/certifi trust store. NEVER False.
            self.tls_verify = True

        self.session = session or requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        """Construct request headers, injecting X-API-Key if available."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: Optional[Tuple[float, float]] = None,
    ) -> Tuple[int, Dict[str, Any], float]:
        """
        Execute an HTTP request against the gateway with strict error sanitization.
        Never logs credentials, authorization headers, or private keys.
        """
        endpoint_url = build_endpoint_url(self.base_url, path)
        headers = self._get_headers()
        req_timeout = timeout or (self.connect_timeout, self.read_timeout)

        start_time = time.perf_counter()
        try:
            response = self.session.request(
                method=method,
                url=endpoint_url,
                json=json_data,
                headers=headers,
                timeout=req_timeout,
                verify=self.tls_verify,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            if response.status_code in (401, 403):
                logger.warning(
                    "Upstream inference gateway returned HTTP %d for %s (authentication failed)",
                    response.status_code,
                    path,
                )
                raise InferenceAuthError(
                    f"Inference authentication failed (HTTP {response.status_code}). Check INFERENCE_API_KEY."
                )

            if 500 <= response.status_code < 600:
                logger.warning(
                    "Upstream inference gateway returned HTTP %d for %s (server error)",
                    response.status_code,
                    path,
                )
                raise InferenceServerError(
                    f"Upstream inference service error (HTTP {response.status_code})."
                )

            if response.status_code >= 400:
                logger.warning(
                    "Upstream inference gateway returned HTTP %d for %s",
                    response.status_code,
                    path,
                )
                raise InferenceClientError(
                    f"Inference client error (HTTP {response.status_code}).",
                    error_code=f"http_{response.status_code}",
                )

            try:
                data = response.json()
            except Exception as exc:
                logger.warning("Upstream returned invalid JSON for %s: %s", path, exc)
                raise InferenceResponseError(
                    "Malformed JSON response received from upstream inference service."
                )

            return response.status_code, data, duration_ms

        except requests.exceptions.SSLError as exc:
            logger.warning(
                "TLS certificate verification failed for %s. Ensure a trusted CA bundle is configured. Error: %s",
                endpoint_url,
                exc,
            )
            raise InferenceTLSError(
                "TLS certificate verification failed. The upstream gateway certificate is untrusted or self-signed."
            )
        except requests.exceptions.ConnectTimeout as exc:
            logger.warning("Connect timeout connecting to %s after %.1fs", endpoint_url, req_timeout[0])
            raise InferenceTimeoutError(
                f"Connection timed out after {req_timeout[0]}s connecting to inference gateway."
            )
        except requests.exceptions.ReadTimeout as exc:
            logger.warning("Read timeout waiting for %s after %.1fs", endpoint_url, req_timeout[1])
            raise InferenceTimeoutError(
                f"Read timed out after {req_timeout[1]}s waiting for inference response."
            )
        except requests.exceptions.ConnectionError as exc:
            logger.warning("Connection failure reaching %s: %s", endpoint_url, exc)
            raise InferenceConnectionError(
                "Failed to establish network connection to inference gateway."
            )


# ==============================================================================
# NLI Verification Client
# ==============================================================================

class NLIClient(BaseInferenceClient):
    """Client for EC2 NLI Verification Microservice."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        verify_path: Optional[str] = None,
        verify_batch_path: Optional[str] = None,
        health_path: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(base_url=base_url or NLI_SERVICE_BASE_URL, **kwargs)
        self.verify_path = verify_path or NLI_VERIFY_PATH
        self.verify_batch_path = verify_batch_path or NLI_VERIFY_BATCH_PATH
        self.health_path = health_path or NLI_HEALTH_PATH

    def check_health(self, timeout: float = 2.0) -> Dict[str, Any]:
        """Check upstream NLI service health with a bounded timeout."""
        try:
            status_code, data, latency = self._request(
                method="GET",
                path=self.health_path,
                timeout=(timeout, timeout),
            )
            return {
                "available": True,
                "status_code": status_code,
                "latency_ms": latency,
                **data,
            }
        except InferenceClientError as exc:
            return {
                "available": False,
                "error": exc.error_code,
                "message": str(exc),
            }
        except Exception as exc:
            return {
                "available": False,
                "error": "unexpected_error",
                "message": str(exc),
            }

    def verify(self, claim: str, evidence: str) -> Dict[str, Any]:
        """
        Verify a single claim against evidence using EC2 NLI service.
        Returns a structured dictionary matching the application verification schema.
        """
        payload = {"claim": claim, "evidence": evidence}
        _, data, latency = self._request(
            method="POST",
            path=self.verify_path,
            json_data=payload,
        )

        status = data.get("status", "Unverified")
        confidence = float(data.get("confidence", 0.0))

        return {
            "status": status,
            "confidence": confidence,
            "scores": data.get("scores", {}),
            "margin": data.get("margin", 0.0),
            "model": data.get("model", "nli-MiniLM2"),
            "inference_mode": data.get("inference_mode", "remote_ec2"),
            "is_real_model": data.get("is_real_model", True),
            "latency_ms": data.get("latency_ms", latency),
            "error": None,
        }

    def verify_batch(self, pairs: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Verify up to 30 claim-evidence pairs in a single batch request.
        """
        if len(pairs) > 30:
            raise InferenceClientError("Batch size cannot exceed 30 pairs per request", error_code="batch_size_exceeded")

        payload = {"pairs": pairs}
        _, data, latency = self._request(
            method="POST",
            path=self.verify_batch_path,
            json_data=payload,
        )

        return {
            "results": data.get("results", []),
            "latency_ms": latency,
            "count": len(data.get("results", [])),
        }


# ==============================================================================
# LLM Correction Client
# ==============================================================================

class LLMCorrectionClient(BaseInferenceClient):
    """Client for EC2 Qwen LLM Text Correction Microservice."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        correct_path: Optional[str] = None,
        health_path: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__(base_url=base_url or LLM_SERVICE_BASE_URL, **kwargs)
        self.correct_path = correct_path or LLM_CORRECT_PATH
        self.health_path = health_path or LLM_HEALTH_PATH

    def check_health(self, timeout: float = 2.0) -> Dict[str, Any]:
        """Check upstream LLM service health with a bounded timeout."""
        try:
            status_code, data, latency = self._request(
                method="GET",
                path=self.health_path,
                timeout=(timeout, timeout),
            )
            return {
                "available": True,
                "status_code": status_code,
                "latency_ms": latency,
                **data,
            }
        except InferenceClientError as exc:
            return {
                "available": False,
                "error": exc.error_code,
                "message": str(exc),
            }
        except Exception as exc:
            return {
                "available": False,
                "error": "unexpected_error",
                "message": str(exc),
            }

    def correct(self, claim: str, evidence: str) -> Dict[str, Any]:
        """
        Request factual correction from EC2 Qwen model using claim and evidence.
        """
        payload = {"claim": claim, "evidence": evidence}
        _, data, latency = self._request(
            method="POST",
            path=self.correct_path,
            json_data=payload,
        )

        return {
            "correction": str(data.get("correction") or "").strip(),
            "tokens_generated": int(data.get("tokens_generated", 0)),
            "abstain": bool(data.get("abstain", False)),
            "model": data.get("model", "Qwen2.5-0.5B-Instruct"),
            "latency_ms": data.get("latency_ms", latency),
            "error": None,
        }


# ==============================================================================
# Thread-safe Singleton Accessors
# ==============================================================================

_CLIENT_LOCK = threading.Lock()
_NLI_CLIENT: Optional[NLIClient] = None
_LLM_CLIENT: Optional[LLMCorrectionClient] = None


def get_nli_client() -> NLIClient:
    """Return or initialize the shared NLIClient instance."""
    global _NLI_CLIENT
    if _NLI_CLIENT is None:
        with _CLIENT_LOCK:
            if _NLI_CLIENT is None:
                _NLI_CLIENT = NLIClient()
    return _NLI_CLIENT


def get_llm_client() -> LLMCorrectionClient:
    """Return or initialize the shared LLMCorrectionClient instance."""
    global _LLM_CLIENT
    if _LLM_CLIENT is None:
        with _CLIENT_LOCK:
            if _LLM_CLIENT is None:
                _LLM_CLIENT = LLMCorrectionClient()
    return _LLM_CLIENT


def reset_clients() -> None:
    """Reset shared client instances (primarily for testing with custom configs)."""
    global _NLI_CLIENT, _LLM_CLIENT
    with _CLIENT_LOCK:
        _NLI_CLIENT = None
        _LLM_CLIENT = None
