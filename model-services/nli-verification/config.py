"""Configuration for the Lightweight NLI Verification Microservice."""
import os

PORT = int(os.getenv("NLI_PORT", "5001"))
HOST = os.getenv("NLI_HOST", "127.0.0.1")

# Default lightweight candidate model
MODEL_NAME = os.getenv("NLI_MODEL_NAME", "cross-encoder/nli-MiniLM2-L6-H768")
ONNX_MODEL_PATH = os.getenv("NLI_ONNX_PATH", "")

# Concurrency control: max concurrent inferences on CPU
MAX_CONCURRENT_INFERENCES = int(os.getenv("NLI_MAX_CONCURRENCY", "2"))

# Confidence threshold calibration (empirically tuned for MiniLM2)
CONFIDENCE_THRESHOLD = float(os.getenv("NLI_THRESHOLD", "0.65"))
MARGIN_THRESHOLD = float(os.getenv("NLI_MARGIN", "0.10"))

# Request timeouts
INFERENCE_TIMEOUT = float(os.getenv("NLI_TIMEOUT", "15.0"))
