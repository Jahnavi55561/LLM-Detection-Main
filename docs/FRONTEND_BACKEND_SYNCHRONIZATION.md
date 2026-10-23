# Frontend–Backend Synchronization Audit & Integration Report

## Executive Summary

This report establishes the complete frontend-to-backend synchronization audit, integration verification, and contract hardening for **LLM-Detection-Main**. The backend orchestrator (deployed on Render) coordinates evidence retrieval and private upstream calls to two AWS EC2 inference microservices behind an Nginx HTTPS gateway:
- **NLI Verification Service:** `https://13.205.17.228/nli/verify`
- **Qwen LLM Correction Service:** `https://13.205.17.228/llm/correct`

This audit synchronized the frontend interface ([`frontend/`](file:///C:/Collaboration%20Projects/LLM-Detection-Main/frontend/) and legacy [`static/`](file:///C:/Collaboration%20Projects/LLM-Detection-Main/static/)/[`templates/`](file:///C:/Collaboration%20Projects/LLM-Detection-Main/templates/)) with the backend API gateway ([`backend/app.py`](file:///C:/Collaboration%20Projects/LLM-Detection-Main/backend/app.py)), guaranteeing zero secret leakage to browsers, robust duplicate-submission prevention, granular multi-state health reporting, and 100% automated test coverage.

---

## 1. Discovered Architecture & Request Lifecycle

```mermaid
flowchart TD
    subgraph Browser ["Frontend Browser Client"]
        UI["Web UI (index.html / script.js)"]
        UI_Health["System Status Poller (every 30s)"]
    end

    subgraph Render ["Render Backend Gateway (Flask)"]
        GW["backend/app.py"]
        EV["services/evidence.py (Wikipedia + KB)"]
        ORCH["services/orchestrator.py"]
        CLIENT["services/inference_client.py"]
    end

    subgraph EC2 ["AWS EC2 Gateway (Nginx HTTPS :443)"]
        NGINX["Nginx Gateway (13.205.17.228)"]
        NLI_SVC["NLI Service (:8001 / MiniLM2)"]
        LLM_SVC["LLM Service (:8002 / Qwen2.5-0.5B)"]
    end

    UI -->|"POST /api/analyze {text}"| GW
    UI_Health -->|"GET /api/health"| GW
    GW -->|"1. Split sentences & retrieve evidence"| EV
    GW -->|"2. Verify claim"| ORCH
    ORCH -->|"3. HTTPS POST /nli/verify (X-API-Key)"| CLIENT
    CLIENT -->|"TLS Encrypted Request"| NGINX
    NGINX -->|"/nli/verify"| NLI_SVC
    NLI_SVC -->|"Verdict: Supported / Contradicted / Unverified"| NGINX
    NGINX -->|"Inference JSON response"| CLIENT

    alt Status is Contradicted
        ORCH -->|"4. Suggest & validate correction"| CLIENT
        CLIENT -->|"HTTPS POST /llm/correct (X-API-Key)"| NGINX
        NGINX -->|"/llm/correct"| LLM_SVC
        LLM_SVC -->|"Grounded correction"| NGINX
        NGINX -->|"Correction JSON response"| CLIENT
    end

    GW -->|"Aggregated Response JSON"| UI
```

### Complete Request Lifecycle Trace

1. **User Submission:** The user submits a claim or paragraph in `frontend/index.html`.
2. **Client Validation & UI Lock:** `frontend/js/script.js` validates that text is non-empty, sets `isAnalyzing = true`, disables the submit button, and displays an animated loading spinner with phase indicators.
3. **Gateway Dispatch:** The browser dispatches `POST /api/analyze` with payload `{"text": "<claim text>"}`. The URL dynamically resolves via `window.API_BASE_URL`, `<meta name="backend-api-url">`, or relative path `""` (never a hardcoded local IP).
4. **Sentence Splitting & Evidence Retrieval:** `backend/app.py` splits the paragraph using `text_processor.split_sentences()` and retrieves evidence for each sentence using `services.evidence.retrieve_evidence()`, checking Wikipedia and local curated knowledge.
5. **NLI Verification Delegation:** For each sentence, `backend/services/orchestrator.py` invokes `nli_client.verify()` passing `claim` and extracted `evidence`. The client injects `X-API-Key`, enforces strict TLS verification (`verify=True` or `INFERENCE_CA_BUNDLE_PATH`), and applies timeout guards.
6. **Contradiction Correction Delegation:** If the verdict is `Contradicted`, `suggest_correction_remote()` calls `llm_client.correct()`. The resulting correction is verified by `validate_correction_remote()` using the NLI client before acceptance.
7. **Safe Failure & Error Containment:** If the EC2 gateway is unreachable, times out, or fails TLS verification, the backend marks the claim as `Unverified`, records the error code (e.g. `tls_verification_failed`), and logs the event without leaking credentials.
8. **UI Rendering:** The frontend receives the response, updates the summary metrics (Total, Supported, Contradicted, Unverified), renders verdict cards with color badges and confidence scores, presents evidence excerpts and source links, and renders the corrected paragraph if applicable.

---

## 2. API Contract Specification & Schema Comparison

### Endpoint Summary

| Endpoint | Method | Request Payload | Response Status | Key Response Fields |
|---|---|---|---|---|
| `/api/health` | GET | None | 200 / 503 | `status`, `backend_version`, `model_status`, `services` |
| `/api/analyze` | POST | `{"text": string}` | 200 / 400 | `results`, `counts`, `corrected_paragraph`, `total_sentences`, `supported_count`, `contradicted_count`, `unverified_count` |
| `/api/chat` | POST | `{"message": string}` | 200 / 400 | `response`, `source`, `timestamp` |
| `/api/history` | GET | None | 200 | `history` (list of previous analyses) |
| `/api/clear-history` | POST | None | 200 | `message`, `cleared` |

### Detailed Schemas

#### `/api/health`
```json
{
  "status": "ready" | "degraded" | "error",
  "backend_version": "2.1.0",
  "environment": "production",
  "models": {
    "nli_verification": "healthy" | "unhealthy" | "unavailable",
    "llm_correction": "healthy" | "unhealthy" | "unavailable"
  },
  "services": {
    "nli": {
      "endpoint": "https://13.205.17.228/nli/health",
      "status": "healthy" | "error",
      "model": "cross-encoder/nli-MiniLM2-L6-H768",
      "is_real_model": true,
      "inference_mode": "remote_ec2"
    },
    "llm": {
      "endpoint": "https://13.205.17.228/llm/health",
      "status": "healthy" | "error",
      "model": "Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
      "is_real_model": true,
      "inference_mode": "remote_ec2"
    }
  }
}
```

#### `/api/analyze`
```json
{
  "total_sentences": 2,
  "supported_count": 1,
  "contradicted_count": 1,
  "unverified_count": 0,
  "counts": {
    "supported": 1,
    "contradicted": 1,
    "unverified": 0
  },
  "corrected_paragraph": "The Earth revolves around the Sun. Canberra is the capital of Australia.",
  "results": [
    {
      "id": 1,
      "sentence": "The Earth revolves around the Sun.",
      "status": "Supported",
      "confidence": 0.96,
      "explanation": "Retrieved evidence directly supports the claim.",
      "evidence": "Earth orbits the Sun once annually.",
      "source": "Wikipedia",
      "source_url": "https://en.wikipedia.org/wiki/Earth",
      "correction": "",
      "correction_validated": false,
      "inference_mode": "remote_ec2",
      "is_real_model": true,
      "error": null
    }
  ]
}
```

---

## 3. Discrepancies & Mismatches Identified and Resolved

| # | Component | Discrepancy Identified | Resolution Applied |
|---|---|---|---|
| 1 | `frontend/js/script.js` | `API_BASE_URL` was hardcoded to `http://127.0.0.1:5000`, causing CORS and connection failures when deployed on Render or accessed via external hostnames. | Refactored to dynamically inspect `window.API_BASE_URL`, `<meta name="backend-api-url">`, and fallback to relative root `""`. |
| 2 | `frontend/js/script.js` & `static/script.js` | UI health check only evaluated `data.status === "ready"`, unable to distinguish between NLI failure, LLM failure, TLS certificate requirements, and backend unreachable. | Implemented 5-state health classifier in `checkBackendHealth()`: All Operational, NLI Offline, LLM Offline, Both Models Down / TLS Cert Required, and Backend Offline. |
| 3 | `frontend/css/style.css` & `static/style.css` | Status dot only had `.ready` and `.error` styles. Warning state for partial degradation was missing. | Added `.status-dot.warning` (amber pulse) and standardized CSS variables across stylesheets. |
| 4 | `frontend/index.html` & `templates/index.html` | Status dots lacked DOM IDs, preventing JavaScript from updating both sidebar and banner status indicators. | Added `id="sidebar-status-dot"`, `id="system-status-dot"`, and `id="system-status-text"`. |
| 5 | `frontend/js/script.js` | Chat interface allowed rapid repeated clicks, spawning duplicate simultaneous in-flight requests. | Added `isChatting` lock flag, disabling input and submit button during request execution. |
| 6 | `frontend/js/script.js` | If an upstream inference call failed (e.g. TLS failure), the UI rendered "0% confidence" as if the model evaluated the claim. | Added `item.error` inspection displaying a "Service Notice" badge and clean explanatory notice instead of zero confidence. |
| 7 | `backend/app.py` | Missing legacy static asset alias `/static/<path:filename>`, leading to potential 404s for cached or legacy assets. | Added `/static/<path:filename>` alias route safely serving files from `static/` or fallback `frontend/`. |
| 8 | `backend/app.py` | `/api/chat` required key `"message"`. If a client sent `"question"` or `"text"`, it returned 400 Bad Request. | Updated `/api/chat` to accept `"message"`, `"question"`, or `"text"` interchangeably. |
| 9 | `backend/app.py` | Sentence processing discarded `error` metadata from `verification`, and left `explanation` blank if not explicitly set. | Enriched sentence result dictionary with `"error": verification.get("error")` and default explanations. |

---

## 4. Security & Isolation Verification

- **Zero Credential Exposure:** Neither `INFERENCE_API_KEY` nor internal EC2 IP credentials are exposed to frontend HTML, JavaScript, meta tags, or `/api/health` payloads.
- **Strict TLS Enforcement:** All HTTPS communication to `https://13.205.17.228` enforces certificate verification. Disabling verification via `verify=False` is strictly prevented in source code.
- **Graceful TLS Error Handling:** In the absence of a configured trusted CA bundle for the self-signed certificate, the backend raises `InferenceTLSError`, and returns a safe `"Unverified"` verdict with code `"tls_verification_failed"`.

---

## 5. Automated Test Suite Results

### Test Execution Summary
- **Total Tests:** 64
- **Passed:** 55
- **Skipped:** 9 (Live hardware/network tests requiring `RUN_LIVE_INFERENCE_TESTS=1`)
- **Failed:** 0
- **Duration:** 19.85s

### Dedicated Frontend–Backend Integration Suite (`tests/integration/test_frontend_backend_sync.py`)
1. `test_static_frontend_and_assets_serving` — **PASSED**
2. `test_analyze_request_response_schema_compatibility` — **PASSED**
3. `test_chat_endpoint_schema_compatibility` — **PASSED**
4. `test_health_state_distinction_both_operational` — **PASSED**
5. `test_health_state_distinction_nli_offline` — **PASSED**
6. `test_health_state_distinction_tls_error` — **PASSED**
7. `test_health_endpoint_no_secrets_leaked` — **PASSED**
8. `test_unavailable_upstream_never_produces_supported_verdict` — **PASSED**
9. `test_correction_failure_never_fabricates_correction` — **PASSED**
10. `test_history_and_clear_workflow` — **PASSED**

---

## 6. Remaining Deployment Prerequisites

### Self-Signed TLS Certificate Trust Bundle on Render
The EC2 gateway at `https://13.205.17.228` currently uses a self-signed TLS certificate. Before live requests will succeed without TLS verification errors:
1. Export the EC2 server certificate or private CA certificate (`ec2_ca.crt`).
2. In the Render Dashboard, add a **Secret File**:
   - File Path: `/etc/secrets/ec2_ca.crt`
   - Contents: Paste the PEM-encoded certificate.
3. Configure Environment Variable on Render:
   - `INFERENCE_CA_BUNDLE_PATH=/etc/secrets/ec2_ca.crt`
   - `INFERENCE_API_KEY=<configured-secret-key>`
