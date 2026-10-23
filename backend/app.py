"""Flask Backend API for Factual Claim Verification and Evidence Orchestration."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import logging
import os
import sys
from typing import Any, Dict

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests

# Support running as standalone script or as a module
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from .config import (
        FRONTEND_DIR,
        HOST,
        LLM_SERVICE_URL,
        MAX_INPUT_CHARS,
        MAX_SENTENCES,
        NLI_SERVICE_URL,
        PORT,
    )
    from .services.evidence import retrieve_evidence
    from .services.inference_client import get_llm_client, get_nli_client
    from .services.orchestrator import (
        build_corrected_paragraph,
        suggest_correction_remote,
        validate_correction_remote,
        verify_claim_remote,
    )
    from .services.text_processor import split_sentences
except ImportError:
    from config import (
        FRONTEND_DIR,
        HOST,
        LLM_SERVICE_URL,
        MAX_INPUT_CHARS,
        MAX_SENTENCES,
        NLI_SERVICE_URL,
        PORT,
    )
    from services.evidence import retrieve_evidence
    from services.inference_client import get_llm_client, get_nli_client
    from services.orchestrator import (
        build_corrected_paragraph,
        suggest_correction_remote,
        validate_correction_remote,
        verify_claim_remote,
    )
    from services.text_processor import split_sentences

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] backend: %(message)s")
logger = logging.getLogger("backend")

app = Flask(__name__, static_folder=None)
CORS(app)

RECENT_HISTORY = deque(maxlen=20)

# Shared bounded thread pool for claim processing
GLOBAL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ClaimWorker")

def _process_claim(idx: int, sentence: str) -> Dict[str, Any]:
    """Execute end-to-end evidence retrieval, NLI verification, and correction for a single claim."""
    try:
        evidence_pack = retrieve_evidence(sentence)
        evidence_text = evidence_pack.get("evidence", "")
        source = evidence_pack.get("source", "")
        source_url = evidence_pack.get("source_url", "")

        verification = verify_claim_remote(claim=sentence, evidence=evidence_text)
        status = verification.get("status", "Unverified")
        confidence = float(verification.get("confidence", 0.0))
        explanation = verification.get("explanation")
        if not explanation:
            if status == "Supported":
                explanation = "Retrieved evidence directly supports the claim."
            elif status == "Contradicted":
                explanation = "Retrieved evidence directly contradicts the claim."
            else:
                explanation = "Evidence is insufficient or inconclusive to confirm the claim."

        correction = ""
        correction_validated = False

        if status == "Contradicted":
            suggested = suggest_correction_remote(claim=sentence, evidence=evidence_text)
            if suggested:
                is_valid = validate_correction_remote(
                    claim=sentence,
                    correction=suggested,
                    evidence=evidence_text
                )
                if is_valid:
                    correction = suggested
                    correction_validated = True

        return {
            "id": idx + 1,
            "sentence": sentence,
            "status": status,
            "confidence": confidence,
            "explanation": explanation,
            "evidence": evidence_text,
            "source": source,
            "source_url": source_url,
            "correction": correction,
            "correction_validated": correction_validated,
            "inference_mode": verification.get("inference_mode", "fallback"),
            "is_real_model": verification.get("is_real_model", False),
            "error": verification.get("error"),
        }
    except Exception as exc:
        logger.exception("Error processing sentence %d: %s", idx, exc)
        return {
            "id": idx + 1,
            "sentence": sentence,
            "status": "Unverified",
            "confidence": 0.0,
            "explanation": "Claim processing encountered an internal error.",
            "evidence": "",
            "source": "",
            "source_url": "",
            "correction": "",
            "correction_validated": False,
            "inference_mode": "fallback",
            "is_real_model": False,
            "error": "internal_error",
        }

# ======================== STATIC FRONTEND ROUTES ========================

@app.get("/")
def serve_frontend_index():
    if os.path.exists(os.path.join(FRONTEND_DIR, "index.html")):
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify({"message": "LLM Hallucination Detection API Gateway"}), 200

@app.get("/css/<path:filename>")
def serve_frontend_css(filename):
    css_dir = os.path.join(FRONTEND_DIR, "css")
    return send_from_directory(css_dir, filename)

@app.get("/js/<path:filename>")
def serve_frontend_js(filename):
    js_dir = os.path.join(FRONTEND_DIR, "js")
    return send_from_directory(js_dir, filename)

@app.get("/static/<path:filename>")
def serve_static_legacy(filename):
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    if os.path.exists(os.path.join(static_dir, filename)):
        return send_from_directory(static_dir, filename)
    return send_from_directory(FRONTEND_DIR, filename)

# ======================== API ROUTES ========================

@app.get("/api/health")
def health():
    nli_client = get_nli_client()
    llm_client = get_llm_client()

    nli_raw = nli_client.check_health(timeout=2.0)
    llm_raw = llm_client.check_health(timeout=2.0)

    # Sanitize upstream health responses to avoid leaking infrastructure details
    nli_health = {
        "available": bool(nli_raw.get("available", False)),
        "status": nli_raw.get("status", "unavailable"),
        "is_real_model_ready": bool(nli_raw.get("is_real_model_ready", False)),
        "inference_mode": nli_raw.get("inference_mode", "remote_ec2"),
        "model": nli_raw.get("model_name") or nli_raw.get("model", "cross-encoder/nli-MiniLM2-L6-H768"),
    }
    if not nli_health["available"]:
        nli_health["error"] = nli_raw.get("error", "unavailable")

    llm_health = {
        "available": bool(llm_raw.get("available", False)),
        "status": llm_raw.get("status", "unavailable"),
        "is_real_model_ready": bool(llm_raw.get("is_real_model_ready", False)),
        "inference_mode": llm_raw.get("inference_mode", "remote_ec2"),
        "model": llm_raw.get("model_name") or llm_raw.get("model", "Qwen2.5-0.5B-Instruct"),
    }
    if not llm_health["available"]:
        llm_health["error"] = llm_raw.get("error", "unavailable")

    return jsonify({
        "ok": True,
        "service": "backend-gateway",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nli_service": nli_health,
        "llm_service": llm_health,
    }), 200

@app.post("/api/analyze")
def analyze():
    data = request.get_json(silent=True) or request.form or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "Please paste text to analyze."}), 400

    if len(text) > MAX_INPUT_CHARS:
        return jsonify({
            "error": f"Text exceeds maximum allowed length of {MAX_INPUT_CHARS} characters."
        }), 413

    sentences = split_sentences(text)
    if not sentences:
        return jsonify({"error": "No valid sentences found in input."}), 400

    if len(sentences) > MAX_SENTENCES:
        return jsonify({
            "error": f"Maximum {MAX_SENTENCES} sentences per analysis allowed."
        }), 400

    results = [None] * len(sentences)
    futures = {
        GLOBAL_EXECUTOR.submit(_process_claim, idx, sentence): idx
        for idx, sentence in enumerate(sentences)
    }

    for future in as_completed(futures):
        idx = futures[future]
        try:
            results[idx] = future.result()
        except Exception as exc:
            logger.error("Future failed for sentence %d: %s", idx, exc)
            results[idx] = {
                "id": idx + 1,
                "sentence": sentences[idx],
                "status": "Unverified",
                "confidence": 0.0,
                "explanation": "Execution error during claim verification.",
                "evidence": "",
                "source": "",
                "source_url": "",
                "correction": "",
                "correction_validated": False,
            }

    counts = {
        "Supported": sum(1 for r in results if r and r["status"] == "Supported"),
        "Contradicted": sum(1 for r in results if r and r["status"] == "Contradicted"),
        "Unverified": sum(1 for r in results if r and r["status"] == "Unverified"),
    }

    corrected_paragraph = build_corrected_paragraph(results)

    response_payload = {
        "results": results,
        "analysis": results,
        "counts": counts,
        "summary": counts,
        "corrected_paragraph": corrected_paragraph,
        "total_sentences": len(results),
        "supported_count": counts["Supported"],
        "contradicted_count": counts["Contradicted"],
        "unverified_count": counts["Unverified"],
    }

    preview = text[:80] + ("…" if len(text) > 80 else "")
    RECENT_HISTORY.appendleft({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "preview": preview,
        "total_sentences": len(results),
        "counts": counts,
        "corrected_paragraph": corrected_paragraph,
    })

    return jsonify(response_payload), 200

@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or data.get("text") or data.get("question") or "").strip()

    if not message:
        return jsonify({"reply": "Please ask a factual question or statement to verify."}), 400

    evidence_pack = retrieve_evidence(message)
    evidence_text = evidence_pack.get("evidence", "")
    source = evidence_pack.get("source", "")
    source_url = evidence_pack.get("source_url", "")

    verification = verify_claim_remote(claim=message, evidence=evidence_text)
    status = verification.get("status", "Unverified")
    confidence = float(verification.get("confidence", 0.0))
    explanation = verification.get("explanation", "")

    reply = f"Claim status: {status}. {explanation}"
    if source:
        reply += f" Source: {source}."

    return jsonify({
        "status": status,
        "confidence": confidence,
        "explanation": explanation,
        "evidence": evidence_text,
        "source": source,
        "source_url": source_url,
        "reply": reply,
    }), 200

@app.get("/api/history")
def history():
    return jsonify({"history": list(RECENT_HISTORY)}), 200

@app.post("/api/history/clear")
@app.delete("/api/history")
def clear_history():
    RECENT_HISTORY.clear()
    return jsonify({"ok": True, "message": "History cleared successfully."}), 200

# ======================== ERROR HANDLERS ========================

@app.errorhandler(400)
def handle_bad_request(exc):
    return jsonify({"error": str(exc)}), 400

@app.errorhandler(413)
def handle_too_large(exc):
    return jsonify({"error": "Payload exceeds maximum allowed size."}), 413

@app.errorhandler(500)
def handle_internal_error(exc):
    logger.exception("Internal server error: %s", exc)
    return jsonify({"error": "An internal server error occurred."}), 500

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
