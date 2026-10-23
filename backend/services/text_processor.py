"""Text processing service: Sentence decomposition and evidence passage extraction."""
import re
from typing import List

ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "vs", "etc", "e.g",
    "i.e", "u.s", "u.k", "ph.d", "gov", "gen", "rep", "sen", "sq", "km",
    "approx", "fig", "al", "inc", "ltd", "corp", "dept", "no", "univ",
    "est", "st", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep",
    "oct", "nov", "dec"
}

def split_sentences(text: str) -> List[str]:
    """
    Decompose paragraph into sentences while preserving decimals,
    abbreviations, single-letter initials (e.g. George W. Bush), and lists.
    """
    text = (text or "").strip()
    if not text:
        return []

    # 1. Protect numeric decimals (e.g. 3.14, 2.5)
    text = re.sub(r"(\d+)\.(\d+)", r"\1<DECIMAL>\2", text)

    # 2. Protect single-letter initials with periods (e.g. "George W. Bush" -> "George W<INITDOT> Bush")
    text = re.sub(r"\b([A-Z])\.\s+(?=[A-Z])", r"\1<INITDOT> ", text)

    # 3. Protect multi-letter abbreviations
    for abbr in sorted(ABBREVIATIONS, key=len, reverse=True):
        pattern = rf"(?i)\b{re.escape(abbr)}\."
        text = re.sub(pattern, lambda m: m.group(0).rstrip(".") + "<DOT>", text)

    # 4. Protect numbered bullet lists (e.g. "1. First claim" or "10. Tenth claim")
    text = re.sub(r"(?m)^(\d+)\.\s+", r"\1<NUMDOT> ", text)
    text = re.sub(r"(?<=[.!?])\s+(\d{1,3})\.\s+", r" \1<NUMDOT> ", text)

    # 5. Split on standard sentence boundaries (newline or punctuation followed by space or quote+space)
    raw_splits = re.split(r"(?:[\r\n]+|(?<=[.!?])[\"']?\s+)", text)
    sentences = []

    for sentence in raw_splits:
        sentence = (
            sentence.replace("<DECIMAL>", ".")
            .replace("<INITDOT>", ".")
            .replace("<DOT>", ".")
            .replace("<NUMDOT>", ".")
        )
        sentence = re.sub(r"\s+", " ", sentence).strip()
        if sentence:
            sentences.append(sentence)

    return sentences

def extract_relevant_passage(evidence: str, claim: str, max_chars: int = 1800) -> str:
    """Extract evidence sentences with the highest lexical overlap to the claim."""
    evidence = (evidence or "").strip()
    if len(evidence) <= max_chars:
        return evidence

    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be",
        "in", "of", "on", "at", "to", "for", "and", "or",
        "that", "this", "it", "with", "as", "by", "from"
    }

    claim_tokens = {
        token for token in re.findall(r"\b[a-z0-9]+\b", claim.lower())
        if token not in stop_words
    }

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", evidence)
        if len(sentence.strip()) > 10
    ]

    if not sentences or not claim_tokens:
        return evidence[:max_chars]

    ranked = []
    for index, sentence in enumerate(sentences):
        sentence_tokens = set(re.findall(r"\b[a-z0-9]+\b", sentence.lower()))
        overlap = len(claim_tokens & sentence_tokens)
        ranked.append((overlap, index, sentence))

    ranked.sort(key=lambda item: item[0], reverse=True)

    if not ranked or ranked[0][0] == 0:
        return evidence[:max_chars]

    selected = []
    total = 0
    for _, _, sentence in ranked:
        if total + len(sentence) + 1 > max_chars:
            continue
        selected.append(sentence)
        total += len(sentence) + 1

    return " ".join(selected)
