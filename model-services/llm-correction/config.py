"""Configuration for the Lightweight LLM Correction Microservice."""
import os

PORT = int(os.getenv("LLM_PORT", "5002"))
HOST = os.getenv("LLM_HOST", "127.0.0.1")

MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")
GGUF_MODEL_PATH = os.getenv("LLM_GGUF_PATH", "")

# Concurrency control: strictly 1-2 concurrent CPU inferences to prevent CPU exhaustion
MAX_CONCURRENT_INFERENCES = int(os.getenv("LLM_MAX_CONCURRENCY", "1"))

# Generation constraints
MAX_NEW_TOKENS = int(os.getenv("LLM_MAX_NEW_TOKENS", "64"))
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
CONTEXT_LIMIT = int(os.getenv("LLM_CONTEXT_LIMIT", "2048"))
GENERATION_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "12.0"))
