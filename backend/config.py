"""Configuration for the Backend API Orchestration Gateway and EC2 Inference Clients."""
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("backend.config")

# Server host and port
HOST = os.getenv("BACKEND_HOST", os.getenv("HOST", "0.0.0.0" if os.getenv("RENDER") else "127.0.0.1"))
PORT = int(os.getenv("PORT", os.getenv("BACKEND_PORT", "5000")))

# CORS configuration: comma-separated origins or "*" (default)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# Default EC2 Gateway Base URL (HTTPS behind Nginx reverse proxy)
DEFAULT_GATEWAY_URL = "https://13.205.17.228"

# ------------------------------------------------------------------------------
# NLI Service Configuration
# ------------------------------------------------------------------------------
NLI_SERVICE_BASE_URL = os.getenv(
    "NLI_SERVICE_BASE_URL",
    os.getenv("NLI_SERVICE_URL", DEFAULT_GATEWAY_URL)
).rstrip("/")
NLI_VERIFY_PATH = os.getenv("NLI_VERIFY_PATH", "/nli/verify")
NLI_VERIFY_BATCH_PATH = os.getenv("NLI_VERIFY_BATCH_PATH", "/nli/verify-batch")
NLI_HEALTH_PATH = os.getenv("NLI_HEALTH_PATH", "/nli/health")

# ------------------------------------------------------------------------------
# LLM Correction Service Configuration
# ------------------------------------------------------------------------------
LLM_SERVICE_BASE_URL = os.getenv(
    "LLM_SERVICE_BASE_URL",
    os.getenv("LLM_SERVICE_URL", DEFAULT_GATEWAY_URL)
).rstrip("/")
LLM_CORRECT_PATH = os.getenv("LLM_CORRECT_PATH", "/llm/correct")
LLM_HEALTH_PATH = os.getenv("LLM_HEALTH_PATH", "/llm/health")

# ------------------------------------------------------------------------------
# Security, TLS, and Authentication
# ------------------------------------------------------------------------------
# API Key for EC2 Gateway (X-API-Key header). Must be read from environment.
INFERENCE_API_KEY = os.getenv("INFERENCE_API_KEY", "")

# Optional custom CA bundle path (PEM format) for self-signed or internal CA verification.
# Never disable TLS verification (verify=False) in production.
INFERENCE_CA_BUNDLE_PATH = os.getenv("INFERENCE_CA_BUNDLE_PATH", "")

# ------------------------------------------------------------------------------
# Timeouts & Retries (in seconds)
# ------------------------------------------------------------------------------
INFERENCE_CONNECT_TIMEOUT = float(os.getenv("INFERENCE_CONNECT_TIMEOUT", "5.0"))
INFERENCE_READ_TIMEOUT = float(os.getenv("INFERENCE_READ_TIMEOUT", "30.0"))
INFERENCE_MAX_RETRIES = int(os.getenv("INFERENCE_MAX_RETRIES", "1"))

# Legacy timeout and URL aliases for backwards compatibility
NLI_TIMEOUT = float(os.getenv("NLI_TIMEOUT", str(INFERENCE_CONNECT_TIMEOUT + INFERENCE_READ_TIMEOUT)))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", str(INFERENCE_CONNECT_TIMEOUT + INFERENCE_READ_TIMEOUT)))
WIKI_TIMEOUT = float(os.getenv("WIKI_TIMEOUT", "6.0"))

NLI_SERVICE_URL = NLI_SERVICE_BASE_URL
LLM_SERVICE_URL = LLM_SERVICE_BASE_URL

# ------------------------------------------------------------------------------
# Input validation guardrails
# ------------------------------------------------------------------------------
MAX_INPUT_CHARS = 10000
MAX_SENTENCES = 30

# File paths
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
KB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "knowledge_base.json"))


def build_endpoint_url(base_url: str, path: str) -> str:
    """Normalize base URL and path to construct a clean HTTP(S) URL."""
    base = (base_url or "").rstrip("/")
    rel_path = (path or "").lstrip("/")
    return f"{base}/{rel_path}"


def validate_inference_config() -> Dict[str, Any]:
    """
    Validate inference client configuration at startup.
    Returns status and sanitized diagnostic info without exposing secrets.
    """
    diagnostics = {
        "nli_base_url": NLI_SERVICE_BASE_URL,
        "llm_base_url": LLM_SERVICE_BASE_URL,
        "has_api_key": bool(INFERENCE_API_KEY.strip()),
        "ca_bundle_configured": bool(INFERENCE_CA_BUNDLE_PATH.strip()),
        "ca_bundle_exists": False,
        "connect_timeout": INFERENCE_CONNECT_TIMEOUT,
        "read_timeout": INFERENCE_READ_TIMEOUT,
        "max_retries": INFERENCE_MAX_RETRIES,
        "valid": True,
        "warnings": [],
    }

    if not diagnostics["has_api_key"]:
        diagnostics["warnings"].append(
            "INFERENCE_API_KEY is not set in environment. Upstream EC2 calls requiring X-API-Key will fail with HTTP 401/403."
        )

    if diagnostics["ca_bundle_configured"]:
        if os.path.exists(INFERENCE_CA_BUNDLE_PATH):
            diagnostics["ca_bundle_exists"] = True
        else:
            diagnostics["valid"] = False
            diagnostics["warnings"].append(
                f"Configured INFERENCE_CA_BUNDLE_PATH does not exist on disk: {INFERENCE_CA_BUNDLE_PATH}"
            )

    return diagnostics
