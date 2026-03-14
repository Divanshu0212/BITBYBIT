"""
Content Metrics — Local Computation of Content Quality Signals
──────────────────────────────────────────────────────────────
Precompute word_count, paragraph_count, readability_score,
grammar_error_count, similarity_ratio, and keyword_coverage
before sending to the LLM for evaluation.
"""

import math
import re
from collections import Counter


def compute_content_metrics(
    content: str,
    required_keywords: list[str] | None = None,
) -> dict:
    """
    Compute all 6 content metrics from raw submission text.
    Returns a flat dict matching the CONTENT_METRICS schema.
    """
    words = _tokenize_words(content)
    sentences = _split_sentences(content)
    paragraphs = _split_paragraphs(content)

    return {
        "word_count": len(words),
        "paragraph_count": len(paragraphs),
        "readability_score": _flesch_kincaid_score(words, sentences),
        "grammar_error_count": _count_grammar_errors(content, sentences),
        "similarity_ratio": _compute_similarity_ratio(content, paragraphs),
        "keyword_coverage": _compute_keyword_coverage(content, required_keywords),
    }


# ── Tokenisation ─────────────────────────────────────────────────────────

def _tokenize_words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text)


def _split_sentences(text: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw if s.strip() and len(s.split()) >= 2]


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


# ── Flesch-Kincaid Readability ───────────────────────────────────────────

def _count_syllables(word: str) -> int:
    """Approximate English syllable count using vowel-group heuristic."""
    word = word.lower().rstrip("e")
    if not word:
        return 1
    count = len(re.findall(r"[aeiouy]+", word))
    return max(count, 1)


def _flesch_kincaid_score(words: list[str], sentences: list[str]) -> float:
    """
    Flesch Reading Ease score (0-100).
    Higher = easier to read.
    """
    if not words or not sentences:
        return 0.0

    total_words = len(words)
    total_sentences = len(sentences)
    total_syllables = sum(_count_syllables(w) for w in words)

    asl = total_words / total_sentences
    asw = total_syllables / total_words

    score = 206.835 - (1.015 * asl) - (84.6 * asw)
    return round(max(0.0, min(100.0, score)), 1)


# ── Grammar Error Detection ─────────────────────────────────────────────

_GRAMMAR_PATTERNS = [
    (r"\b(i)\b(?!['.])(?<![A-Z])", "lowercase_i"),
    (r"\b(a)\s+(a|e|i|o|u)\w+", "a_before_vowel"),
    (r"\b(an)\s+[^aeiouAEIOU\s]\w+", "an_before_consonant"),
    (r"\b(\w+)\s+\1\b", "repeated_word"),
    (r"\s{2,}", "multiple_spaces"),
    (r"\b(their|there|they're)\b.*\b(their|there|they're)\b", None),
    (r"[.!?]{3,}", "excessive_punctuation"),
    (r"\b(dont|doesnt|cant|wont|isnt|arent|wasnt|werent|hasnt|havent|hadnt|shouldnt|wouldnt|couldnt)\b",
     "missing_apostrophe"),
    (r",\s*(and|but|or|so)\s*,", "comma_splice"),
    (r"(?<![.!?])\n[a-z]", "sentence_start_lowercase"),
]


def _count_grammar_errors(text: str, sentences: list[str]) -> int:
    """
    Detect common grammar errors with pattern matching.
    Returns total error count. Production should use LanguageTool or similar.
    """
    error_count = 0
    for pattern, _ in _GRAMMAR_PATTERNS:
        error_count += len(re.findall(pattern, text, re.IGNORECASE if _ is None else 0))

    for s in sentences:
        words = s.split()
        if len(words) > 50:
            error_count += 1
        if len(words) < 3 and not re.match(r"^[A-Z#]", s):
            error_count += 1

    return error_count


# ── Similarity / Originality ────────────────────────────────────────────

def _ngrams(text: str, n: int = 4) -> list[str]:
    words = _tokenize_words(text.lower())
    if len(words) < n:
        return []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def _compute_similarity_ratio(text: str, paragraphs: list[str]) -> float:
    """
    Self-similarity ratio: how much internal content is duplicated.
    Returns 0.0 (fully unique) to 1.0 (fully duplicated).

    In production, replace with external plagiarism API (Copyscape, Turnitin).
    """
    if len(paragraphs) < 2:
        return 0.0

    all_ngrams = _ngrams(text)
    if not all_ngrams:
        return 0.0

    total = len(all_ngrams)
    unique = len(set(all_ngrams))

    if total == 0:
        return 0.0

    duplication = 1 - (unique / total)

    half = len(paragraphs) // 2
    first_half = " ".join(paragraphs[:half])
    second_half = " ".join(paragraphs[half:])
    first_ngrams = set(_ngrams(first_half))
    second_ngrams = set(_ngrams(second_half))

    if not first_ngrams or not second_ngrams:
        return round(duplication, 3)

    overlap = len(first_ngrams & second_ngrams)
    cross_sim = overlap / min(len(first_ngrams), len(second_ngrams))

    ratio = (duplication * 0.4) + (cross_sim * 0.6)
    return round(min(1.0, ratio), 3)


# ── Keyword Coverage ─────────────────────────────────────────────────────

def _compute_keyword_coverage(text: str, required_keywords: list[str] | None) -> float:
    """
    Fraction of required keywords found in the text (0.0 to 1.0).
    Uses case-insensitive word-boundary matching.
    """
    if not required_keywords:
        return 1.0

    text_lower = text.lower()
    found = 0
    for kw in required_keywords:
        pattern = r"\b" + re.escape(kw.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found += 1

    return round(found / len(required_keywords), 3)
