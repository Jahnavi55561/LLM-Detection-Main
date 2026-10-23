"""Unit tests for evidence retrieval, local knowledge base, and Wikipedia integration."""
from unittest.mock import patch, MagicMock
from backend.services.evidence import (
    is_personal_claim,
    _kb_lookup,
    _generate_queries,
    retrieve_evidence,
)

def test_personal_claim_detection():
    assert is_personal_claim("My friend has a red bicycle.") is True
    assert is_personal_claim("The professor in my class was late.") is True
    assert is_personal_claim("Near my house there is a bakery.") is True
    assert is_personal_claim("The Earth orbits the Sun.") is False
    assert is_personal_claim("Canberra is the capital of Australia.") is False

def test_local_kb_exact_and_fuzzy_match():
    # Exact claim present in knowledge_base.json
    res = _kb_lookup("The Earth revolves around the Sun.")
    assert res is not None
    assert "orbit" in res["evidence"].lower() or "earth" in res["evidence"].lower()
    assert res["retrieval"] == "exact local knowledge-base match"

    # Non-existent claim
    assert _kb_lookup("Completely fabricated unknown alien claim 12345.") is None

def test_query_generation_bounds():
    claim = "The capital of Australia is Canberra and it was chosen in 1908."
    queries = _generate_queries(claim)
    assert len(queries) <= 3
    assert any("Canberra" in q or "Australia" in q for q in queries)

@patch("backend.services.evidence._wiki_search")
@patch("backend.services.evidence._wiki_extracts_batch")
def test_retrieve_evidence_wikipedia_success(mock_extracts, mock_search):
    mock_search.return_value = [{"pageid": 101, "title": "Australia"}]
    mock_extracts.return_value = {
        101: {
            "extract": "Canberra is the capital city of the Commonwealth of Australia.",
            "url": "https://en.wikipedia.org/wiki/Australia"
        }
    }

    result = retrieve_evidence("Canberra is the capital of Australia.")
    assert "Canberra" in result["evidence"]
    assert "Wikipedia — Australia" in result["source"]
    assert result["relevance_score"] > 0

@patch("backend.services.evidence._wiki_search")
def test_retrieve_evidence_handles_api_failure_gracefully(mock_search):
    mock_search.side_effect = Exception("Wikipedia connection error")
    result = retrieve_evidence("An arbitrary query that triggers an exception.")
    assert result["evidence"] == ""
    assert result["retrieval"] == "no relevant evidence found"
