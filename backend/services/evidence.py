"""Evidence retrieval service using local knowledge base and Wikipedia public API."""
import difflib
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from ..config import KB_PATH, WIKI_TIMEOUT
except (ImportError, ValueError):
    from config import KB_PATH, WIKI_TIMEOUT

logger = logging.getLogger("backend.evidence")

WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": "LLMHallucinationFramework/2.0 (https://github.com/educational-prototype; contact: framework@local.net)"
}

STOP = set("""
a about above after again against all am an and any are aren't as at be because been before being below between both
but by can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further had
hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his how how's i
i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor not of off on
once only or other ought our ours ourselves out over own same shan't she she'd she'll she's should shouldn't so some
such than that that's the their theirs them themselves then there there's these they they'd they'll they're they've
this those through to too under until up very was wasn't we we'd we'll we're we've were weren't what what's when
when's where where's which while who who's whom why why's with won't would wouldn't you you'd you'll you're you've
your yours yourself yourselves
""".split())

PERSONAL_PATTERN = re.compile(
    r"\b(my\s+(neighbour|neighbor|friend|professor|college|class|house|teacher|family|boss|colleague|cousin|sister|brother|dad|mom|father|mother|dog|cat|car|laptop|phone|roommate|room)|"
    r"in\s+my\s+class|near\s+my\s+house|at\s+my\s+college|my\s+college\s+library|the\s+user\s+has|the\s+user\s+is|"
    r"a\s+student\s+in\s+my|a\s+person\s+named\s+[a-z]+)\b",
    re.IGNORECASE
)

# Bounded in-memory cache
_CACHE: Dict[str, Any] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 3600
_MAX_CACHE_SIZE = 1000

# Persistent HTTP session
_SESSION = requests.Session()
_retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
_SESSION.mount("https://", HTTPAdapter(max_retries=_retries, pool_connections=10, pool_maxsize=20))

# KB Cache
_KB_CACHE = None
_KB_MTIME = 0

def is_personal_claim(claim: str) -> bool:
    """Detect subjective, private observations not verifiable from public encyclopedias."""
    return bool(PERSONAL_PATTERN.search(claim))

def _tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOP and len(w) > 1}

def _load_kb() -> List[Dict[str, Any]]:
    global _KB_CACHE, _KB_MTIME
    try:
        if os.path.exists(KB_PATH):
            mtime = os.path.getmtime(KB_PATH)
            if _KB_CACHE is not None and mtime == _KB_MTIME:
                return _KB_CACHE
            with open(KB_PATH, "r", encoding="utf-8") as f:
                _KB_CACHE = json.load(f)
                _KB_MTIME = mtime
                return _KB_CACHE
    except Exception as exc:
        logger.error("Failed to load knowledge base: %s", exc)
    return []

def _kb_lookup(claim: str) -> Optional[Dict[str, Any]]:
    claim_norm = re.sub(r"\W+", " ", claim.lower()).strip()
    if not claim_norm:
        return None

    best_match = None
    best_ratio = 0.0

    for item in _load_kb():
        if not isinstance(item, dict):
            continue
        cand = str(item.get("claim", ""))
        cand_norm = re.sub(r"\W+", " ", cand.lower()).strip()

        if cand_norm and cand_norm == claim_norm:
            return {
                "evidence": str(item.get("evidence", "")),
                "source": str(item.get("source", "Local knowledge base")),
                "source_url": str(item.get("source_url", "")),
                "retrieval": "exact local knowledge-base match",
                "relevance_score": 1.0
            }

        ratio = difflib.SequenceMatcher(None, claim_norm, cand_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = item

    if best_match and best_ratio >= 0.88:
        return {
            "evidence": str(best_match.get("evidence", "")),
            "source": str(best_match.get("source", "Local knowledge base")),
            "source_url": str(best_match.get("source_url", "")),
            "retrieval": f"fuzzy local knowledge-base match ({round(best_ratio, 2)})",
            "relevance_score": round(best_ratio, 3)
        }

    return None

def _generate_queries(claim: str) -> List[str]:
    """Generate concise, bounded search queries from a factual claim."""
    q = claim.strip().rstrip(".!?")
    queries = []

    # 1. Named entities (capitalized phrases)
    entities = re.findall(r"\b[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+)*\b", q)
    for ent in entities:
        ent = ent.strip()
        if ent.lower() not in {"the", "a", "an", "all", "every", "one", "zero", "first", "scientists", "researchers", "nasa"}:
            if ent not in queries:
                queries.append(ent)

    # 2. Key content words
    words = [w for w in re.findall(r"[A-Za-z0-9'-]+", q) if w.lower() not in STOP]
    if len(words) >= 2:
        queries.append(" ".join(words[:5]))

    # 3. Full query (bounded)
    queries.append(q[:80])

    # Deduplicate while preserving order, max 3 queries to avoid Wikipedia rate limits
    seen, out = set(), []
    for item in queries:
        clean = item.strip()
        if clean and clean.lower() not in seen and len(clean) > 1:
            out.append(clean)
            seen.add(clean.lower())
    return out[:3]

def _wiki_search(query: str) -> List[Dict[str, Any]]:
    try:
        response = _SESSION.get(
            WIKI_API,
            params={
                "action": "query", "list": "search", "srsearch": query,
                "srlimit": 3, "format": "json", "utf8": 1
            },
            headers=HEADERS,
            timeout=WIKI_TIMEOUT
        )
        if response.status_code == 429:
            logger.warning("Wikipedia API rate limit (429) hit. Backing off.")
            return []
        response.raise_for_status()
        return response.json().get("query", {}).get("search", [])
    except Exception as exc:
        logger.debug("Wikipedia search failed for '%s': %s", query, exc)
        return []

def _wiki_extracts_batch(pageids: List[int]) -> Dict[int, Dict[str, str]]:
    if not pageids:
        return {}
    pageids_str = "|".join(str(pid) for pid in pageids[:6])
    try:
        response = _SESSION.get(
            WIKI_API,
            params={
                "action": "query", "pageids": pageids_str, "prop": "extracts|info",
                "explaintext": 1, "exintro": 1, "inprop": "url",
                "format": "json", "redirects": 1
            },
            headers=HEADERS,
            timeout=WIKI_TIMEOUT + 2
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        results = {}
        for pid_str, page_data in pages.items():
            try:
                pid = int(pid_str)
                results[pid] = {
                    "extract": page_data.get("extract", ""),
                    "url": page_data.get("fullurl", "")
                }
            except (ValueError, TypeError):
                continue
        return results
    except Exception as exc:
        logger.debug("Wikipedia batch extract failed: %s", exc)
        return {}

def retrieve_evidence(claim: str) -> Dict[str, Any]:
    """Retrieve evidence for a claim from cache, local KB, or Wikipedia with resource bounds."""
    key = claim.strip().lower()
    now = time.time()

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and (now - cached[0] < _CACHE_TTL):
            return dict(cached[1])

    # Guard 1: Personal assertion check
    if is_personal_claim(claim):
        res = {
            "evidence": "",
            "source": "",
            "source_url": "",
            "retrieval": "personal_claim",
            "relevance_score": 0.0
        }
        with _CACHE_LOCK:
            _CACHE[key] = (now, res)
        return res

    # Guard 2: Local KB check
    local = _kb_lookup(claim)
    if local and local.get("evidence"):
        with _CACHE_LOCK:
            _CACHE[key] = (now, local)
        return dict(local)

    # Guard 3: Wikipedia query & extracts
    queries = _generate_queries(claim)
    query_results = {}
    try:
        for query in queries:
            for item in _wiki_search(query):
                pageid = item.get("pageid")
                if pageid and pageid not in query_results:
                    query_results[pageid] = item

        all_pageids = list(query_results.keys())[:6]
        page_extracts = _wiki_extracts_batch(all_pageids)

        claim_tokens = _tokens(claim)
        candidates = []

        for pageid, result in query_results.items():
            extract_info = page_extracts.get(pageid)
            if not extract_info:
                continue
            extract = extract_info.get("extract", "").strip()
            url = extract_info.get("url", "")
            if not extract:
                continue

            title = result.get("title", "")
            ev_tokens = _tokens(title + " " + extract[:2500])
            if not claim_tokens:
                continue

            overlap = len(claim_tokens & ev_tokens) / len(claim_tokens)
            title_boost = 0.20 if (claim_tokens & _tokens(title)) else 0.0
            score = overlap + title_boost
            candidates.append((score, title, extract, url))

        candidates.sort(key=lambda x: x[0], reverse=True)

        if candidates and candidates[0][0] >= 0.18:
            score, title, extract, url = candidates[0]
            res = {
                "evidence": extract[:3000],
                "source": f"Wikipedia — {title}",
                "source_url": url,
                "retrieval": "Wikipedia API",
                "relevance_score": round(score, 3)
            }
        else:
            res = {
                "evidence": "",
                "source": "",
                "source_url": "",
                "retrieval": "no relevant evidence found",
                "relevance_score": 0.0
            }
    except Exception as exc:
        logger.warning("Evidence retrieval encountered exception for '%s': %s", claim, exc)
        res = {
            "evidence": "",
            "source": "",
            "source_url": "",
            "retrieval": "no relevant evidence found",
            "relevance_score": 0.0
        }

    with _CACHE_LOCK:
        if len(_CACHE) >= _MAX_CACHE_SIZE:
            old_keys = sorted(_CACHE.keys(), key=lambda k: _CACHE[k][0])[: len(_CACHE) // 4]
            for k in old_keys:
                _CACHE.pop(k, None)
        _CACHE[key] = (now, res)

    return dict(res)
