"""Unit tests for sentence decomposition and passage extraction."""
from backend.services.text_processor import split_sentences, extract_relevant_passage

def test_split_sentences_basic():
    text = "The Earth revolves around the Sun. Canberra is Australia's capital."
    sentences = split_sentences(text)
    assert len(sentences) == 2
    assert sentences[0] == "The Earth revolves around the Sun."
    assert sentences[1] == "Canberra is Australia's capital."

def test_split_sentences_with_decimals():
    text = "The inflation rate dropped to 2.5% in Q3. Gross margin was 3.14 times higher."
    sentences = split_sentences(text)
    assert len(sentences) == 2
    assert "2.5%" in sentences[0]
    assert "3.14" in sentences[1]

def test_split_sentences_with_abbreviations():
    text = "Dr. Smith visited the U.S. embassy. Prof. Johnson arrived later at approx. 5 p.m."
    sentences = split_sentences(text)
    assert len(sentences) == 2
    assert "Dr. Smith" in sentences[0]
    assert "U.S." in sentences[0]
    assert "Prof. Johnson" in sentences[1]

def test_split_sentences_with_name_initials():
    text = "George W. Bush was the 43rd president. He was born in Connecticut."
    sentences = split_sentences(text)
    assert len(sentences) == 2
    assert sentences[0] == "George W. Bush was the 43rd president."
    assert sentences[1] == "He was born in Connecticut."

def test_split_sentences_numbered_bullets():
    text = "1. First factual claim.\n2. Second factual claim.\n3. Third factual claim."
    sentences = split_sentences(text)
    assert len(sentences) == 3
    assert "First factual claim." in sentences[0]
    assert "Second factual claim." in sentences[1]
    assert "Third factual claim." in sentences[2]

def test_split_sentences_empty_or_whitespace():
    assert split_sentences("") == []
    assert split_sentences("   \n\t  ") == []
    assert split_sentences(None) == []

def test_extract_relevant_passage_selects_overlapping_sentences():
    evidence = (
        "Jupiter is the largest planet in our solar system. "
        "Canberra is the capital city of Australia, selected in 1908. "
        "Python is a popular programming language created by Guido van Rossum."
    )
    claim = "What is the capital of Australia?"
    passage = extract_relevant_passage(evidence, claim)
    assert "Canberra" in passage
    assert "Australia" in passage
