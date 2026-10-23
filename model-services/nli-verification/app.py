"""Lightweight NLI Verification Microservice Flask API."""
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
        ONNX_MODEL_PATH,
        MAX_CONCURRENT_INFERENCES,
        CONFIDENCE_THRESHOLD,
        MARGIN_THRESHOLD,
        PORT,
        HOST,
    )
    from .model_runner import NLIModelRunner
except ImportError:
    from config import (
        MODEL_NAME,
        ONNX_MODEL_PATH,
        MAX_CONCURRENT_INFERENCES,
        CONFIDENCE_THRESHOLD,
        MARGIN_THRESHOLD,
        PORT,
        HOST,
    )
    from model_runner import NLIModelRunner

from flask import Flask, jsonify, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] nli_service: %(message)s")
logger = logging.getLogger("nli_service")

app = Flask(__name__)

runner = NLIModelRunner(
    model_name=MODEL_NAME,
    onnx_path=ONNX_MODEL_PATH,
    max_concurrency=MAX_CONCURRENT_INFERENCES,
    threshold=CONFIDENCE_THRESHOLD,
    margin=MARGIN_THRESHOLD,
)

# Initialize runner at startup
runner.initialize()

@app.get("/health")
def health():
    st = runner.status()
    return jsonify({
        "service": "nli-verification",
        **st
    }), 200

@app.post("/verify")
def verify():
    data = request.get_json(silent=True) or {}
    claim = str(data.get("claim") or "").strip()
    evidence = str(data.get("evidence") or "").strip()

    if not claim:
        return jsonify({"error": "Missing 'claim' parameter in request"}), 400

    result = runner.predict(premise=evidence, hypothesis=claim)
    return jsonify(result), 200

@app.post("/verify-batch")
def verify_batch():
    data = request.get_json(silent=True) or {}
    pairs = data.get("pairs") or []

    if not isinstance(pairs, list):
        return jsonify({"error": "'pairs' must be a list of objects containing claim and evidence"}), 400

    if len(pairs) > 30:
        return jsonify({"error": "Batch size cannot exceed 30 pairs per request"}), 400

    results = []
    for item in pairs:
        claim = str(item.get("claim") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        results.append(runner.predict(premise=evidence, hypothesis=claim))

    return jsonify({"results": results}), 200

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
