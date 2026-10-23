"use strict";

/* =========================================================
   LLM HALLUCINATION DETECTION FRAMEWORK — FRONTEND CONTROLLER
   Decoupled Static Frontend Client
   ========================================================= */

// Support configurable backend base URL for separated deployment (Render, custom domain, CDN)
const API_BASE_URL = (function() {
    if (typeof window !== "undefined" && window.API_BASE_URL) {
        return String(window.API_BASE_URL).replace(/\/+$/, "");
    }
    if (typeof document !== "undefined") {
        const meta = document.querySelector('meta[name="backend-api-url"]');
        if (meta && meta.content) {
            return meta.content.trim().replace(/\/+$/, "");
        }
    }
    return "";
})();

const $ = (id) => document.getElementById(id);

const inputText = $("input-text");
const analyzeBtn = $("analyze-btn");
const clearInputBtn = $("clear-input-btn");
const charCount = $("char-count");
const messageBox = $("message");
const resultsSection = $("results");
const resultList = $("result-list");
const correctedParagraph = $("corrected-paragraph");
const copyBtn = $("copy-btn");

const supportedCount = $("supported-count");
const contradictedCount = $("contradicted-count");
const unverifiedCount = $("unverified-count");
const totalCount = $("total-count");

const chatForm = $("chat-form");
const chatInput = $("chat-input");
const chatBtn = $("chat-btn");
const chatResult = $("chat-result");

const historyList = $("history-list");
const clearHistoryBtn = $("clear-history-btn");

let statusChart = null;
let comparisonChart = null;
let latestCorrectedText = "";
let isAnalyzing = false;

/* ---------- SAFE STRING & URL SANITIZERS ---------- */

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

function safeUrl(value) {
    try {
        const url = new URL(String(value || ""));
        if (url.protocol === "https:" || url.protocol === "http:") {
            return url.href;
        }
    } catch (_) {}
    return "";
}

function normalizeStatus(value) {
    const status = String(value || "").trim().toLowerCase();
    if (status === "supported") return "Supported";
    if (status === "contradicted") return "Contradicted";
    return "Unverified";
}

function getCount(counts, key) {
    if (!counts) return 0;
    const capitalizedKey = key.charAt(0).toUpperCase() + key.slice(1);
    const candidates = [
        counts[key],
        counts[capitalizedKey],
        counts[`${key}_count`],
        counts[`${capitalizedKey.toLowerCase()}_count`]
    ];
    for (const candidate of candidates) {
        if (candidate !== undefined && candidate !== null) {
            const value = Number(candidate);
            if (Number.isFinite(value)) return value;
        }
    }
    return 0;
}

function normalizeCounts(counts = {}) {
    return {
        Supported: getCount(counts, "supported"),
        Contradicted: getCount(counts, "contradicted"),
        Unverified: getCount(counts, "unverified")
    };
}

function setMessage(text, type = "info") {
    if (!messageBox) return;
    messageBox.textContent = text;
    messageBox.className = `message-${type}`;
}

function clearMessage() {
    if (!messageBox) return;
    messageBox.textContent = "";
    messageBox.className = "";
}

async function apiRequest(path, options = {}) {
    const url = `${API_BASE_URL}${path}`;
    const response = await fetch(url, {
        ...options,
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...(options.headers || {})
        }
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || data.message || `Request failed (${response.status})`);
    }
    return data;
}

/* ---------- CHARACTER COUNTER ---------- */

function updateCharacterCount() {
    if (!inputText || !charCount) return;
    charCount.textContent = `${inputText.value.length.toLocaleString()} / 10000 characters`;
}

if (inputText) {
    inputText.addEventListener("input", updateCharacterCount);
    updateCharacterCount();
}

/* ---------- STATISTICS ---------- */

function updateStatistics(counts = {}, total = null) {
    const normalized = normalizeCounts(counts);
    const supported = normalized.Supported;
    const contradicted = normalized.Contradicted;
    const unverified = normalized.Unverified;
    const calculatedTotal = supported + contradicted + unverified;
    const parsedTotal = total === null ? NaN : Number(total);
    const finalTotal = Number.isFinite(parsedTotal) ? parsedTotal : calculatedTotal;

    if (supportedCount) supportedCount.textContent = supported;
    if (contradictedCount) contradictedCount.textContent = contradicted;
    if (unverifiedCount) unverifiedCount.textContent = unverified;
    if (totalCount) totalCount.textContent = finalTotal;

    updateCharts(supported, contradicted, unverified);
}

/* ---------- CHARTS ---------- */

function updateCharts(supported, contradicted, unverified) {
    if (typeof Chart === "undefined") {
        console.warn("Chart.js is unavailable.");
        return;
    }

    const donutCanvas = $("status-chart");
    const barCanvas = $("comparison-chart");
    if (!donutCanvas || !barCanvas) return;

    const values = [supported, contradicted, unverified];
    const labels = ["Supported", "Contradicted", "Unverified"];

    if (!statusChart) {
        statusChart = new Chart(donutCanvas, {
            type: "doughnut",
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: ["#34d399", "#fb7185", "#fbbf24"],
                    borderColor: "#111a2e",
                    borderWidth: 4,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            color: "#c7d3e9",
                            padding: 18,
                            usePointStyle: true
                        }
                    }
                }
            }
        });
    } else {
        statusChart.data.datasets[0].data = values;
        statusChart.update();
    }

    if (!comparisonChart) {
        comparisonChart = new Chart(barCanvas, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Number of claims",
                    data: values,
                    backgroundColor: [
                        "rgba(52, 211, 153, 0.8)",
                        "rgba(251, 113, 133, 0.8)",
                        "rgba(251, 191, 36, 0.8)"
                    ],
                    borderRadius: 8,
                    maxBarThickness: 55
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: {
                        ticks: { color: "#c7d3e9" },
                        grid: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: "#96a4c1", precision: 0 },
                        grid: { color: "rgba(150,164,193,0.12)" }
                    }
                }
            }
        });
    } else {
        comparisonChart.data.datasets[0].data = values;
        comparisonChart.update();
    }
}

/* ---------- RENDER RESULT ---------- */

function renderResult(item, index = 0) {
    const status = normalizeStatus(item.status);
    const claim = item.sentence || item.claim || item.text || "No claim text provided.";
    const rawConfidence = Number(item.confidence);
    const confidenceText = (Number.isFinite(rawConfidence) && rawConfidence > 0)
        ? `${Math.round(rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence)}% confidence`
        : "";

    const explanation = item.explanation || item.reason || "";
    const evidence = item.evidence || "";
    const correction = item.correction || "";
    const source = item.source || "";
    const sourceUrl = safeUrl(item.source_url || item.url);
    const hasServiceError = Boolean(item.error && item.error !== "insufficient_evidence" && item.error !== "empty_claim");

    let html = `
        <article class="result" data-result-index="${index}">
            <div class="result-head">
                <div class="badges">
                    <span class="badge ${status}">${status}</span>
                    ${confidenceText ? `<span class="confidence">${escapeHtml(confidenceText)}</span>` : ""}
                    ${item.demo ? `<span class="badge" style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4);">Predefined Demo</span>` : ""}
                    ${hasServiceError ? `<span class="badge" style="background: rgba(251, 191, 36, 0.2); color: var(--amber);">Service Notice</span>` : ""}
                </div>
                <span class="muted">Claim ${index + 1}</span>
            </div>
            <p class="claim">${escapeHtml(claim)}</p>
    `;

    if (explanation) {
        html += `<p class="detail">${escapeHtml(explanation)}</p>`;
    }

    if (evidence) {
        html += `
            <div class="evidence">
                <strong>Evidence</strong>
                <p>${escapeHtml(evidence)}</p>
            </div>
        `;
    }

    if (source) {
        html += `<p class="source-label">Source: ${escapeHtml(source)}</p>`;
    }

    if (sourceUrl) {
        html += `
            <a class="source" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">
                Open evidence source ↗
            </a>
        `;
    }

    if (correction && item.correction_validated !== false) {
        html += `
            <div class="correction">
                <strong>Suggested correction</strong>
                <p>${escapeHtml(correction)}</p>
            </div>
        `;
    }

    html += "</article>";
    return html;
}

/* ---------- ANALYZE ---------- */

async function analyzeText() {
    if (isAnalyzing) return;
    const text = inputText?.value.trim() || "";

    if (!text) {
        setMessage("Please enter some text to analyze.", "error");
        inputText?.focus();
        return;
    }

    if (text.length > 10000) {
        setMessage("Text exceeds the 10,000-character limit.", "error");
        return;
    }

    isAnalyzing = true;
    clearMessage();

    if (analyzeBtn) {
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = "Analyzing...";
    }

    if (resultsSection) resultsSection.hidden = true;

    try {
        const payload = { text };
        const data = await apiRequest("/api/analyze", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        if (!Array.isArray(data.results)) {
            throw new Error(data.error || "The server did not return analysis results.");
        }

        if (resultList) {
            resultList.innerHTML = data.results.length
                ? data.results.map(renderResult).join("")
                : '<p class="muted">No sentences were found to analyze.</p>';
        }

        const counts = data.counts || data.summary || {
            Supported: data.supported_count ?? 0,
            Contradicted: data.contradicted_count ?? 0,
            Unverified: data.unverified_count ?? 0
        };

        const calculatedCounts = { Supported: 0, Contradicted: 0, Unverified: 0 };
        data.results.forEach((item) => {
            calculatedCounts[normalizeStatus(item.status)]++;
        });

        const normalizedCounts = normalizeCounts(counts);
        const countsTotal = normalizedCounts.Supported + normalizedCounts.Contradicted + normalizedCounts.Unverified;
        const finalCounts = countsTotal === data.results.length ? normalizedCounts : calculatedCounts;

        updateStatistics(finalCounts, data.total_sentences ?? data.results.length);
        latestCorrectedText = data.corrected_paragraph || "";

        if (correctedParagraph) {
            correctedParagraph.textContent = latestCorrectedText ||
                "No validated corrections were available. Review the individual claims and evidence above.";
        }

        if (resultsSection) resultsSection.hidden = false;

        setMessage(`Analysis complete. Processed ${data.total_sentences ?? data.results.length} sentence(s).`, "success");
        await loadHistory();
        resultsSection?.scrollIntoView({ behavior: "smooth", block: "start" });

    } catch (error) {
        console.error("Analysis failed:", error);
        setMessage(`Analysis failed: ${error.message}. Check that the backend services are running.`, "error");
    } finally {
        isAnalyzing = false;
        if (analyzeBtn) {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = "✦ Analyze & Verify";
        }
    }
}

if (analyzeBtn) {
    analyzeBtn.addEventListener("click", analyzeText);
}

if (inputText) {
    inputText.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
            analyzeText();
        }
    });
}

if (clearInputBtn) {
    clearInputBtn.addEventListener("click", () => {
        if (inputText) inputText.value = "";
        updateCharacterCount();
        clearMessage();
        inputText?.focus();
    });
}

if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
        const text = latestCorrectedText || correctedParagraph?.textContent?.trim() || "";
        if (!text) {
            setMessage("There is no corrected text to copy.", "error");
            return;
        }
        try {
            await navigator.clipboard.writeText(text);
            setMessage("Corrected paragraph copied.", "success");
        } catch (error) {
            console.error("Copy failed:", error);
            setMessage("Clipboard access failed. Select the paragraph and copy it manually.", "error");
        }
    });
}

/* ---------- DEMO MODE CONTROLLER ---------- */

function initDemoControls() {
    const select = $("demo-claim-select");
    const runBtn = $("run-demo-btn");
    const loadClaimBtn = $("load-demo-claim-btn");

    if (select && typeof DEMO_DATASET !== "undefined") {
        select.innerHTML = '<option value="">-- Choose a predefined claim to demo (30 available) --</option>';

        const supportedGroup = document.createElement("optgroup");
        supportedGroup.label = "15 Supported Factual Claims";

        const contradictedGroup = document.createElement("optgroup");
        contradictedGroup.label = "15 Contradicted Factual Claims";

        DEMO_DATASET.forEach((item) => {
            const opt = document.createElement("option");
            opt.value = String(item.id);
            opt.textContent = `${item.id}. [${item.status}] ${item.claim}`;
            if (item.status === "Supported") {
                supportedGroup.appendChild(opt);
            } else {
                contradictedGroup.appendChild(opt);
            }
        });

        select.appendChild(supportedGroup);
        select.appendChild(contradictedGroup);

        select.addEventListener("change", () => {
            const selectedId = select.value;
            if (!selectedId) return;
            const item = getDemoClaimById(selectedId);
            if (item && inputText) {
                inputText.value = item.claim;
                updateCharacterCount();
            }
        });
    }

    if (loadClaimBtn) {
        loadClaimBtn.addEventListener("click", () => {
            const select = $("demo-claim-select");
            const selectedId = select?.value;
            if (!selectedId) {
                setMessage("Please select a claim from the demo dropdown first.", "error");
                return;
            }
            runSingleDemoClaim(Number(selectedId));
        });
    }

    if (runBtn) {
        runBtn.addEventListener("click", () => {
            runFullDemoDataset();
        });
    }
}

function runSingleDemoClaim(claimId) {
    if (typeof DEMO_DATASET === "undefined") {
        setMessage("Demo dataset module is loading or unavailable.", "error");
        return;
    }
    const item = getDemoClaimById(claimId);
    if (!item) {
        setMessage("Selected demo claim could not be found.", "error");
        return;
    }

    if (inputText) {
        inputText.value = item.claim;
        updateCharacterCount();
    }

    clearMessage();

    const demoResultItem = {
        id: 1,
        sentence: item.claim,
        claim: item.claim,
        status: item.status,
        confidence: null,
        explanation: `Predefined demonstration result (expected classification: ${item.status}). Live AI inference was not performed.`,
        evidence: "Predefined demo result — live evidence retrieval was not performed.",
        source: "Client Predefined Demo Dataset",
        source_url: "",
        correction: item.status === "Contradicted" ? "(Predefined contradiction - correction omitted in demo)" : "",
        demo: true
    };

    if (resultList) {
        resultList.innerHTML = renderResult(demoResultItem, 0);
    }

    const counts = {
        Supported: item.status === "Supported" ? 1 : 0,
        Contradicted: item.status === "Contradicted" ? 1 : 0,
        Unverified: 0
    };

    updateStatistics(counts, 1);

    if (correctedParagraph) {
        correctedParagraph.textContent = item.status === "Contradicted"
            ? "Predefined demo claim is contradicted. (Live correction model bypassed in demo mode)."
            : "Claim is verified as Supported by predefined evaluation dataset.";
    }

    if (resultsSection) resultsSection.hidden = false;
    setMessage(`Deterministic demo mode: Displaying predefined outcome for Claim #${item.id} (${item.status}). Live inference was bypassed.`, "success");
    resultsSection?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function runFullDemoDataset() {
    if (typeof DEMO_DATASET === "undefined") {
        setMessage("Demo dataset module is loading or unavailable.", "error");
        return;
    }
    const stats = getDemoCounts();

    clearMessage();

    const demoResults = DEMO_DATASET.map((item, idx) => ({
        id: idx + 1,
        sentence: item.claim,
        claim: item.claim,
        status: item.status,
        confidence: null,
        explanation: `Predefined demonstration result (expected classification: ${item.status}). Live AI inference was not performed.`,
        evidence: "Predefined demo result — live evidence retrieval was not performed.",
        source: "Client Predefined Demo Dataset",
        source_url: "",
        correction: "",
        demo: true
    }));

    if (resultList) {
        resultList.innerHTML = demoResults.map(renderResult).join("");
    }

    updateStatistics(stats.counts, stats.total);

    if (correctedParagraph) {
        correctedParagraph.textContent = "Demonstration dataset contains 15 Supported claims and 15 Contradicted claims. Live correction generation was bypassed.";
    }

    if (resultsSection) resultsSection.hidden = false;
    setMessage(`Deterministic demo mode: Verified all ${stats.total} predefined dataset claims (${stats.supported} Supported, ${stats.contradicted} Contradicted). Live AI inference was bypassed.`, "success");
    resultsSection?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- CHAT ASSISTANT ---------- */

let isChatting = false;

if (chatForm) {
    chatForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (isChatting) return;

        const question = chatInput?.value.trim() || "";
        if (!question) {
            if (chatResult) chatResult.textContent = "Please enter a question.";
            return;
        }

        isChatting = true;
        if (chatBtn) {
            chatBtn.disabled = true;
            chatBtn.textContent = "Checking...";
        }
        if (chatResult) {
            chatResult.textContent = "Searching available evidence...";
        }

        try {
            const payload = { message: question };
            const data = await apiRequest("/api/chat", {
                method: "POST",
                body: JSON.stringify(payload)
            });

            const status = normalizeStatus(data.status);
            const reply = data.reply || data.explanation || "No detailed response was returned.";
            const rawConfidence = Number(data.confidence);
            const confidenceHtml = (Number.isFinite(rawConfidence) && rawConfidence > 0)
                ? `<span class="confidence">${Math.round(rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence)}% confidence</span>`
                : "";
            const sourceUrl = safeUrl(data.source_url);

            if (chatResult) {
                chatResult.innerHTML = `
                    <article class="result">
                        <div class="badges">
                            <span class="badge ${status}">${status}</span>
                            ${confidenceHtml}
                        </div>
                        <p class="claim">${escapeHtml(question)}</p>
                        <p class="detail">${escapeHtml(reply)}</p>
                        ${data.source ? `<p class="source-label">Source: ${escapeHtml(data.source)}</p>` : ""}
                        ${sourceUrl ? `<a class="source" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>` : ""}
                    </article>
                `;
            }
        } catch (error) {
            console.error("Chat request failed:", error);
            if (chatResult) {
                chatResult.textContent = `Could not get an answer: ${error.message}.`;
            }
        } finally {
            isChatting = false;
            if (chatBtn) {
                chatBtn.disabled = false;
                chatBtn.textContent = "Ask Assistant";
            }
        }
    });
}

/* ---------- HISTORY ---------- */

function renderHistoryItem(item) {
    const preview = item.preview || item.text || "Previous analysis";
    const counts = normalizeCounts(item.counts || item.summary || {});
    const timestamp = item.timestamp || item.time || "";

    let formattedTime = timestamp;
    if (timestamp) {
        const parsed = new Date(timestamp);
        if (!Number.isNaN(parsed.getTime())) {
            formattedTime = parsed.toLocaleString();
        }
    }

    return `
        <article class="history-item">
            <p>${escapeHtml(preview)}</p>
            <div class="badges">
                <span class="badge Supported">Supported: ${counts.Supported}</span>
                <span class="badge Contradicted">Contradicted: ${counts.Contradicted}</span>
                <span class="badge Unverified">Unverified: ${counts.Unverified}</span>
            </div>
            ${formattedTime ? `<small>${escapeHtml(formattedTime)}</small>` : ""}
        </article>
    `;
}

async function loadHistory() {
    if (!historyList) return;
    try {
        const data = await apiRequest("/api/history");
        const history = Array.isArray(data) ? data : (data.history || []);
        if (!history.length) {
            historyList.innerHTML = '<p class="muted">No analysis history yet. Analyze some text to get started.</p>';
            return;
        }
        historyList.innerHTML = history.map(renderHistoryItem).join("");
    } catch (error) {
        historyList.innerHTML = '<p class="muted">Could not load history.</p>';
    }
}

if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener("click", async () => {
        if (!window.confirm("Clear all recent analysis history?")) return;
        clearHistoryBtn.disabled = true;
        try {
            await apiRequest("/api/history/clear", {
                method: "POST",
                body: JSON.stringify({})
            });
            await loadHistory();
            setMessage("Recent history cleared.", "success");
        } catch (error) {
            setMessage(`Could not clear history: ${error.message}`, "error");
        } finally {
            clearHistoryBtn.disabled = false;
        }
    });
}

/* ---------- BACKEND HEALTH ---------- */

async function checkBackendHealth() {
    const statusElement = $("sidebar-status");
    const sidebarDot = $("sidebar-status-dot") || document.querySelector(".sidebar-bottom .status-dot");
    const systemStatusText = $("system-status-text");
    const systemStatusDot = $("system-status-dot");

    try {
        const data = await apiRequest("/api/health");
        const nliAvail = Boolean(data.nli_service && data.nli_service.available);
        const llmAvail = Boolean(data.llm_service && data.llm_service.available);
        const nliReal = Boolean(data.nli_service && data.nli_service.is_real_model_ready);
        const llmReal = Boolean(data.llm_service && data.llm_service.is_real_model_ready);

        let statusText = "Connected";
        let badgeText = "Lightweight AI Tier";
        let dotClass = "ready";

        if (!data.ok) {
            statusText = "Check backend status";
            badgeText = "Backend Degraded";
            dotClass = "warning";
        } else if (nliAvail && llmAvail) {
            if (nliReal && llmReal) {
                statusText = "All Models Operational (EC2)";
                badgeText = "EC2 Production Tier";
                dotClass = "ready";
            } else {
                statusText = "Connected (Fallback Mode)";
                badgeText = "Fallback Mode";
                dotClass = "warning";
            }
        } else if (!nliAvail && !llmAvail) {
            const isTls = (data.nli_service?.error === "tls_verification_failed" || data.llm_service?.error === "tls_verification_failed");
            statusText = isTls ? "Inference TLS Cert Required" : "Inference Services Offline";
            badgeText = isTls ? "TLS Cert Needed" : "Models Offline";
            dotClass = "warning";
        } else if (!nliAvail) {
            statusText = "NLI Service Unavailable";
            badgeText = "NLI Offline";
            dotClass = "warning";
        } else if (!llmAvail) {
            statusText = "LLM Service Unavailable";
            badgeText = "LLM Offline";
            dotClass = "warning";
        }

        if (statusElement) statusElement.textContent = statusText;
        if (systemStatusText) systemStatusText.textContent = badgeText;
        if (sidebarDot) sidebarDot.className = `status-dot ${dotClass}`;
        if (systemStatusDot) systemStatusDot.className = `status-dot ${dotClass}`;

    } catch (error) {
        if (statusElement) statusElement.textContent = "Backend unavailable";
        if (systemStatusText) systemStatusText.textContent = "Backend Offline";
        if (sidebarDot) sidebarDot.className = "status-dot error";
        if (systemStatusDot) systemStatusDot.className = "status-dot error";
        console.warn("Backend health check failed:", error);
    }
}

/* ---------- NAVIGATION ---------- */

document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
        document.querySelectorAll(".nav-link").forEach((item) => {
            item.classList.remove("active");
        });
        link.classList.add("active");
    });
});

/* ---------- INITIALIZE ---------- */

updateStatistics({ Supported: 0, Contradicted: 0, Unverified: 0 });
loadHistory();
checkBackendHealth();
initDemoControls();
