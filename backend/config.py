"""Configuration for the Backend API Orchestration Gateway."""
import os

HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
PORT = int(os.getenv("BACKEND_PORT", "5000"))

# Microservice endpoints
NLI_SERVICE_URL = os.getenv("NLI_SERVICE_URL", "http://127.0.0.1:5001")
LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://127.0.0.1:5002")

# Timeouts in seconds
NLI_TIMEOUT = float(os.getenv("NLI_TIMEOUT", "8.0"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "10.0"))
WIKI_TIMEOUT = float(os.getenv("WIKI_TIMEOUT", "6.0"))

# Input validation guardrails
MAX_INPUT_CHARS = 10000
MAX_SENTENCES = 30

# Static frontend folder for optional local serving
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
KB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "knowledge_base.json"))
