"""Orchestration service coordinating remote NLI verification and LLM correction microservices."""
import logging
from typing import Any, Dict, List, Optional

try:
    from .inference_client import (
        InferenceAuthError,
        InferenceClientError,
        InferenceConnectionError,
        InferenceServerError,
        InferenceTimeoutError,
        InferenceTLSError,
        get_llm_client,
        get_nli_client,
    )
    from .text_processor import extract_relevant_passage
except (ImportError, ValueError):
    from services.inference_client import (
        InferenceAuthError,
        InferenceClientError,
        InferenceConnectionError,
        InferenceServerError,
        InferenceTimeoutError,
        InferenceTLSError,
        get_llm_client,
        get_nli_client,
    )
    from services.text_processor import extract_relevant_passage

logger = logging.getLogger("backend.orchestrator")


def verify_claim_remote(claim: str, evidence: str) -> Dict[str, Any]:
    """
    Call the EC2 NLI verification microservice with timeout, security, and circuit defense.
    Distinguishes genuine verdicts from service errors and TLS failures.
    """
    claim = (claim or "").strip()
    evidence = (evidence or "").strip()

    if not claim:
        return {
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "No claim provided.",
            "error": "empty_claim",
            "is_real_model": False,
        }

    if len(evidence) < 30:
        return {
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "Insufficient evidence available to determine factual validity.",
            "error": "insufficient_evidence",
            "is_real_model": False,
        }

    passage = extract_relevant_passage(evidence, claim)
    if not passage:
        passage = evidence[:1800]

    try:
        nli_client = get_nli_client()
        result = nli_client.verify(claim=claim, evidence=passage)

        status = result.get("status", "Unverified")
        if status == "Supported":
            explanation = "Retrieved evidence directly supports the claim."
        elif status == "Contradicted":
            explanation = "Retrieved evidence directly contradicts the claim."
        else:
            explanation = "Evidence is insufficient or inconclusive to confirm the claim."

        result["explanation"] = explanation
        return result

    except InferenceTLSError as exc:
        logger.warning("NLI verification failed due to TLS error: %s", exc)
        return {
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "Inference TLS certificate verification failed. A trusted CA bundle is required.",
            "error": "tls_verification_failed",
            "is_real_model": False,
        }
    except InferenceAuthError as exc:
        logger.warning("NLI verification failed due to authentication error: %s", exc)
        return {
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "Inference service authentication failed. Verify INFERENCE_API_KEY.",
            "error": "upstream_unauthorized",
            "is_real_model": False,
        }
    except InferenceTimeoutError as exc:
        logger.warning("NLI verification timed out: %s", exc)
        return {
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "Inference verification timed out; safe unverified fallback applied.",
            "error": "upstream_timeout",
            "is_real_model": False,
        }
    except InferenceConnectionError as exc:
        logger.warning("NLI verification connection failure: %s", exc)
        return {
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "Inference service unreachable; safe unverified fallback applied.",
            "error": "upstream_connection_error",
            "is_real_model": False,
        }
    except InferenceServerError as exc:
        logger.warning("NLI verification server error: %s", exc)
        return {
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "Inference service encountered a server error; safe unverified fallback applied.",
            "error": "upstream_server_error",
            "is_real_model": False,
        }
    except Exception as exc:
        logger.warning("NLI verification unexpected error: %s", exc)
        return {
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "Verification service unavailable; safe unverified fallback applied.",
            "error": "service_unavailable",
            "is_real_model": False,
        }


def suggest_correction_remote(claim: str, evidence: str) -> str:
    """
    Call the EC2 Qwen correction microservice with timeout and validation constraints.
    Never fabricates a correction if the remote model fails or abstains.
    """
    claim = (claim or "").strip()
    evidence = (evidence or "").strip()

    if not claim or not evidence:
        return ""

    try:
        llm_client = get_llm_client()
        result = llm_client.correct(claim=claim, evidence=evidence)

        if result.get("abstain") is True:
            return ""

        correction = str(result.get("correction") or "").strip()
        if correction.upper() in {"NONE", "N/A", "UNKNOWN"}:
            return ""

        return correction

    except InferenceClientError as exc:
        logger.warning("LLM correction service error: %s", exc)
        return ""
    except Exception as exc:
        logger.warning("LLM correction unexpected error: %s", exc)
        return ""


def validate_correction_remote(claim: str, correction: str, evidence: str) -> bool:
    """
    Validate proposed correction using the NLI microservice.
    A correction is accepted ONLY if the evidence explicitly supports the correction statement.
    """
    if not correction or not evidence:
        return False

    # Correction cannot be identical to the original contradicted claim
    if correction.strip().lower().rstrip(".!?") == claim.strip().lower().rstrip(".!?"):
        return False

    # Verify if evidence entails the correction
    nli_result = verify_claim_remote(claim=correction, evidence=evidence)
    return nli_result.get("status") == "Supported" and nli_result.get("confidence", 0.0) >= 0.60


def build_corrected_paragraph(results: List[Dict[str, Any]]) -> str:
    """Construct a coherent paragraph preserving document flow and unverified claims."""
    sentences = []
    for item in results:
        if not item or not isinstance(item, dict):
            continue
        status = item.get("status")
        orig = item.get("sentence", "").strip()

        if status == "Contradicted" and item.get("correction") and item.get("correction_validated") is True:
            sentences.append(item.get("correction", "").strip())
        else:
            if orig:
                sentences.append(orig)

    return " ".join(sentences)
