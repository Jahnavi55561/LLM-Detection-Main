"""Lightweight LLM Correction Microservice Flask API."""
import logging
import os
import sys

# Support running as a standalone script or as a module
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from .config import (
        MODEL_NAME,
        GGUF_MODEL_PATH,
        MAX_CONCURRENT_INFERENCES,
        MAX_NEW_TOKENS,
        TEMPERATURE,
        CONTEXT_LIMIT,
        PORT,
        HOST,
    )
    from .generator import LLMCorrectionGenerator
except ImportError:
    from config import (
        MODEL_NAME,
        GGUF_MODEL_PATH,
        MAX_CONCURRENT_INFERENCES,
        MAX_NEW_TOKENS,
        TEMPERATURE,
        CONTEXT_LIMIT,
        PORT,
        HOST,
    )
    from generator import LLMCorrectionGenerator

from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] llm_service: %(message)s")
logger = logging.getLogger("llm_service")

app = Flask(__name__)

generator = LLMCorrectionGenerator(
    model_name=MODEL_NAME,
    gguf_path=GGUF_MODEL_PATH,
    max_concurrency=MAX_CONCURRENT_INFERENCES,
    max_new_tokens=MAX_NEW_TOKENS,
    temperature=TEMPERATURE,
    context_limit=CONTEXT_LIMIT,
)

# Initialize generator at startup
generator.initialize()

@app.get("/health")
def health():
    st = generator.status()
    return jsonify({
        "service": "llm-correction",
        **st
    }), 200

@app.post("/correct")
def correct():
    data = request.get_json(silent=True) or {}
    claim = str(data.get("claim") or "").strip()
    evidence = str(data.get("evidence") or "").strip()

    if not claim:
        return jsonify({"error": "Missing 'claim' parameter in request"}), 400

    if not evidence:
        return jsonify({
            "correction": "",
            "message": "Insufficient evidence provided for grounded correction",
            "tokens_generated": 0,
            "latency_ms": 0.0
        }), 200

    result = generator.generate_correction(claim=claim, evidence=evidence)
    return jsonify(result), 200

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
