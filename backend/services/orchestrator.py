"""Orchestration service coordinating remote NLI verification and LLM correction microservices."""
import logging
from typing import Any, Dict, List, Optional
import requests

try:
    from ..config import NLI_SERVICE_URL, LLM_SERVICE_URL, NLI_TIMEOUT, LLM_TIMEOUT
    from .text_processor import extract_relevant_passage
except (ImportError, ValueError):
    from config import NLI_SERVICE_URL, LLM_SERVICE_URL, NLI_TIMEOUT, LLM_TIMEOUT
    from services.text_processor import extract_relevant_passage

logger = logging.getLogger("backend.orchestrator")

def verify_claim_remote(claim: str, evidence: str) -> Dict[str, Any]:
    """Call the independent NLI verification microservice with timeout and circuit defense."""
    claim = (claim or "").strip()
    evidence = (evidence or "").strip()

    if not claim:
        return {
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "No claim provided.",
            "error": "empty_claim"
        }

    if len(evidence) < 30:
        return {
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "Insufficient evidence available to determine factual validity.",
            "error": "insufficient_evidence"
        }

    passage = extract_relevant_passage(evidence, claim)

    try:
        url = f"{NLI_SERVICE_URL.rstrip('/')}/verify"
        response = requests.post(
            url,
            json={"claim": claim, "evidence": passage},
            timeout=NLI_TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "Unverified")
            confidence = float(data.get("confidence", 0.0))

            if status == "Supported":
                explanation = "Retrieved evidence directly supports the claim."
            elif status == "Contradicted":
                explanation = "Retrieved evidence directly contradicts the claim."
            else:
                explanation = "Evidence is insufficient or inconclusive to confirm the claim."

            return {
                "status": status,
                "confidence": confidence,
                "explanation": explanation,
                "scores": data.get("scores", {}),
                "model": data.get("model", "nli-service"),
                "inference_mode": data.get("inference_mode", "unknown"),
                "is_real_model": data.get("is_real_model", False),
                "latency_ms": data.get("latency_ms", 0.0)
            }
        else:
            logger.warning("NLI service returned HTTP %d: %s", response.status_code, response.text)
    except requests.exceptions.Timeout:
        logger.warning("NLI verification request timed out after %.1fs", NLI_TIMEOUT)
    except requests.exceptions.ConnectionError:
        logger.warning("NLI service unreachable at %s", NLI_SERVICE_URL)
    except Exception as exc:
        logger.warning("NLI verification failed: %s", exc)

    return {
        "status": "Unverified",
        "confidence": 0.0,
        "explanation": "Verification service unavailable; safe unverified fallback applied.",
        "error": "service_unavailable"
    }

def suggest_correction_remote(claim: str, evidence: str) -> str:
    """Call the independent LLM correction microservice with timeout and validation constraints."""
    claim = (claim or "").strip()
    evidence = (evidence or "").strip()

    if not claim or not evidence:
        return ""

    try:
        url = f"{LLM_SERVICE_URL.rstrip('/')}/correct"
        response = requests.post(
            url,
            json={"claim": claim, "evidence": evidence},
            timeout=LLM_TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            return str(data.get("correction") or "").strip()
        else:
            logger.warning("LLM service returned HTTP %d: %s", response.status_code, response.text)
    except requests.exceptions.Timeout:
        logger.warning("LLM correction request timed out after %.1fs", LLM_TIMEOUT)
    except requests.exceptions.ConnectionError:
        logger.warning("LLM service unreachable at %s", LLM_SERVICE_URL)
    except Exception as exc:
        logger.warning("LLM correction failed: %s", exc)

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
