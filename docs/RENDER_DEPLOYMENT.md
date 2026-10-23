# Render Deployment & EC2 Inference Integration Guide

**Project:** LLM-Detection-Main<br>
**Application Architecture:** Decoupled Microservices
- **Orchestration Backend & Frontend:** Deployed on [Render](https://render.com) (Lightweight Python Flask / Waitress)
- **AI Inference Microservices:** Deployed on AWS EC2 (`ap-south-1`, Mumbai) behind Nginx HTTPS Gateway (`https://13.205.17.228`)

---

## 1. Overview & Architecture

The application separates factual verification and correction into a lightweight web orchestrator and dedicated model inference microservices.

```
┌─────────────────────────────────┐
│     Client Web Browser          │
└──────────────┬──────────────────┘
               │ HTTPS (Public Web)
               ▼
┌─────────────────────────────────┐
│    Render Web Service           │
│    (Flask Orchestrator API)     │
└──────────────┬──────────────────┘
               │ HTTPS + X-API-Key + Strict TLS Verification
               ▼
┌─────────────────────────────────┐
│    AWS EC2 Nginx Gateway        │
│    https://13.205.17.228:443    │
├────────────────┬────────────────┤
│ /nli/*         │ /llm/*         │
▼                ▼                ▼
[NLI Service]    [LLM Service]
Port 5001        Port 5002
(MiniLM2 ONNX)   (Qwen2.5 GGUF)
```

### Security & Privacy Rules
- **No Direct Browser Access:** Clients never communicate directly with the EC2 gateway. All requests pass through the Render orchestrator.
- **No Credential Leaks:** The `INFERENCE_API_KEY` is never returned in client responses, logged in server logs, or committed to source control.
- **No Insecure TLS:** Production environments **must never disable TLS verification** (`verify=False`, `curl -k`, or insecure HTTP clients are strictly disallowed).

---

## 2. Environment Variables Configuration

Set the following environment variables in the Render Dashboard (**Dashboard > Your Web Service > Environment**):

| Variable Name | Required | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `NLI_SERVICE_BASE_URL` | Optional | `https://13.205.17.228` | Base URL of the NLI verification microservice gateway. |
| `NLI_VERIFY_PATH` | Optional | `/nli/verify` | Path for single-claim NLI verification requests. |
| `NLI_VERIFY_BATCH_PATH` | Optional | `/nli/verify-batch` | Path for batch NLI verification requests (up to 30 claims). |
| `NLI_HEALTH_PATH` | Optional | `/nli/health` | Path for upstream NLI health checks. |
| `LLM_SERVICE_BASE_URL` | Optional | `https://13.205.17.228` | Base URL of the Qwen text-correction microservice gateway. |
| `LLM_CORRECT_PATH` | Optional | `/llm/correct` | Path for factual text correction requests. |
| `LLM_HEALTH_PATH` | Optional | `/llm/health` | Path for upstream LLM health checks. |
| `INFERENCE_API_KEY` | **Required** | *(None)* | **Secret API Key** sent via `X-API-Key` to the EC2 gateway. Configure as a private variable. |
| `INFERENCE_CA_BUNDLE_PATH` | **Required for Self-Signed Certs** | *(Empty)* | Absolute path to the trusted CA certificate (PEM format) on Render. |
| `INFERENCE_CONNECT_TIMEOUT`| Optional | `5` | Maximum seconds allowed to establish TCP/TLS connection with gateway. |
| `INFERENCE_READ_TIMEOUT` | Optional | `30` | Maximum seconds allowed to wait for inference response before timing out. |
| `INFERENCE_MAX_RETRIES` | Optional | `1` | Retry attempts for idempotent requests. |

---

## 3. Configuring the Secret API Key on Render

1. Open your service in the [Render Dashboard](https://dashboard.render.com).
2. Navigate to **Environment** in the left sidebar.
3. Click **Add Environment Variable**.
4. Set:
   - **Key:** `INFERENCE_API_KEY`
   - **Value:** `your-secret-gateway-api-key`
5. Click **Save Changes**. Render will automatically redeploy the service with the updated secret.

> [!IMPORTANT]
> Never hardcode `INFERENCE_API_KEY` in `backend/config.py`, `.env.example`, or any file committed to Git. The backend exclusively reads this secret from the runtime environment.

---

## 4. TLS Certificate Verification & The Self-Signed Gateway Certificate

The EC2 gateway at `https://13.205.17.228` currently uses a **self-signed TLS certificate**.

> [!CAUTION]
> Disabling TLS verification (`verify=False` or bypassing SSL) exposes API keys and verification traffic to interception and Man-in-the-Middle (MitM) attacks. The backend enforces strict verification by default.
>
> If trusted TLS is not established, the backend fails safely by marking claims as `Unverified` with `error: "tls_verification_failed"`, rather than bypassing security.

Choose one of the two solutions below to establish trusted TLS:

---

### Option A: Public Trusted Certificate via Domain & Let's Encrypt (Recommended for Production)

If a custom domain or subdomain is pointed to the EC2 Elastic IP:

1. Create a DNS `A` record pointing to the EC2 IP:
   ```text
   inference.yourdomain.com -> 13.205.17.228
   ```
2. On the EC2 instance, install Certbot and issue an automated certificate:
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d inference.yourdomain.com
   ```
3. Update Render environment variables:
   - `NLI_SERVICE_BASE_URL=https://inference.yourdomain.com`
   - `LLM_SERVICE_BASE_URL=https://inference.yourdomain.com`
   - Leave `INFERENCE_CA_BUNDLE_PATH` **empty** (the standard Mozilla / certifi trust store in Python automatically trusts Let's Encrypt).

---

### Option B: Mount the Self-Signed CA Certificate via Render "Secret Files"

If retaining the IP address (`https://13.205.17.228`) with the existing self-signed certificate:

1. **Obtain the certificate from the EC2 instance:**
   On the EC2 host, copy the certificate PEM file (e.g. `/etc/ssl/certs/nginx-selfsigned.crt` or `ec2_ca.crt`):
   ```bash
   cat /etc/ssl/certs/nginx-selfsigned.crt
   ```
2. **Mount the Certificate in Render:**
   - In the Render Dashboard, go to **Environment > Secret Files**.
   - Click **Add Secret File**.
   - **Filename:** `ec2_ca.crt`
   - **Contents:** Paste the complete certificate text including the PEM headers:
     ```text
     -----BEGIN CERTIFICATE-----
     MIID... (certificate contents)
     -----END CERTIFICATE-----
     ```
   - Click **Save Changes**. Render automatically mounts this file at:
     ```text
     /etc/secrets/ec2_ca.crt
     ```
3. **Configure the Environment Variable:**
   - In Render **Environment Variables**, add:
     ```text
     INFERENCE_CA_BUNDLE_PATH=/etc/secrets/ec2_ca.crt
     ```
   - Click **Save Changes**. The backend will now verify the self-signed gateway certificate against `/etc/secrets/ec2_ca.crt`.

---

## 5. Health Checks & Verification

### 5.1 Checking Service Health
Once deployed, verify the system status by issuing a GET request to the Render backend:

```bash
curl https://your-app.onrender.com/api/health
```

**Expected Response (Healthy & Real Model Connected):**
```json
{
  "ok": true,
  "service": "backend-gateway",
  "timestamp": "2026-10-23T18:00:00.000000Z",
  "nli_service": {
    "available": true,
    "status": "healthy_real_model",
    "is_real_model_ready": true,
    "inference_mode": "remote_ec2",
    "model": "cross-encoder/nli-MiniLM2-L6-H768"
  },
  "llm_service": {
    "available": true,
    "status": "healthy_real_model",
    "is_real_model_ready": true,
    "inference_mode": "remote_ec2",
    "model": "Qwen2.5-0.5B-Instruct"
  }
}
```

### 5.2 Diagnostics for Unresolved Prerequisite / Failure Modes

| Health Status Response | Root Cause | Remediation |
| :--- | :--- | :--- |
| `nli_service.error: "tls_verification_failed"` | The EC2 gateway certificate is self-signed and no valid CA bundle was mounted. | Mount the certificate via Render Secret Files and set `INFERENCE_CA_BUNDLE_PATH=/etc/secrets/ec2_ca.crt`. |
| `nli_service.error: "upstream_unauthorized"` | `INFERENCE_API_KEY` is missing or does not match the key on the EC2 Nginx gateway. | Verify `INFERENCE_API_KEY` in Render Environment settings. |
| `nli_service.error: "upstream_connection_error"` | Cannot connect to port 443 on `13.205.17.228`. | Verify EC2 Security Group allows inbound HTTPS (port 443) from `0.0.0.0/0`. Verify Nginx is running (`sudo systemctl status nginx`). |
| `nli_service.error: "upstream_timeout"` | Inference processing exceeded connect/read timeout. | Check EC2 CPU load or increase `INFERENCE_READ_TIMEOUT=45`. |

---

## 6. Local Testing with Environment Variables

To test the integration locally before deploying to Render:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Populate `INFERENCE_API_KEY` and optional `INFERENCE_CA_BUNDLE_PATH` in `.env`.
3. Run the automated test suite:
   ```bash
   pytest tests/ -v
   ```
4. Start the backend:
   ```bash
   python backend/app.py
   ```
5. Test claim verification:
   ```bash
   curl -X POST http://127.0.0.1:5000/api/analyze \
        -H "Content-Type: application/json" \
        -d '{"text": "The Earth revolves around the Sun. The capital of Australia is Sydney."}'
   ```

---

## 7. Render Static Site Deployment (Frontend)

To deploy the static web frontend on Render:

1. In the [Render Dashboard](https://dashboard.render.com), click **New + > Static Site**.
2. Connect the GitHub repository: `https://github.com/Jahnavi55561/LLM-Detection-Main`.
3. Configure the Static Site settings:
   - **Name:** `llm-detection-frontend` (or your preferred name)
   - **Branch:** `main`
   - **Build Command:** *(Leave blank — no build step required)*
   - **Publish Directory:** `frontend`
4. Click **Create Static Site**.
5. The static frontend will be deployed on a high-availability CDN. It automatically connects to the backend at `https://llm-detection-api.onrender.com` via `<meta name="backend-api-url" content="https://llm-detection-api.onrender.com">`.
6. **CORS Allowlist (Optional):** The backend Web Service allows all origins (`*`) by default. To restrict access solely to your static frontend origin, add an environment variable to the backend Web Service:
   ```text
   CORS_ORIGINS=https://llm-detection-frontend.onrender.com
   ```
