"""Deterministic evaluation metrics.

These are cheap, explainable, and need no API key, which makes them good CI
gates. They are also crude: token overlap cannot tell "available" from "not
available". That is why ``evals/judge`` measures how well an evaluator agrees
with human labels before we trust it (article 04).
"""
from __future__ import annotations

import re

from app.text import split_sentences, tokenize

_CITATION = re.compile(r"\s*\[[a-z0-9-]+#\d+\]")


def strip_citations(text: str) -> str:
    return _CITATION.sub("", text).strip()


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def contains_all_facts(answer: str, facts: list[str]) -> tuple[bool, list[str]]:
    """Correctness as 'every expected key fact appears in the answer'."""
    norm_answer = f" {normalize(answer)} "
    missing = [f for f in facts if f" {normalize(f)} " not in norm_answer]
    return not missing, missing


def sentence_support(sentence: str, contexts: list[str]) -> float:
    """Share of the sentence's content words found in the best single context."""
    words = set(tokenize(sentence))
    if not words:
        return 1.0
    best = 0.0
    for ctx in contexts:
        ctx_words = set(tokenize(ctx))
        best = max(best, len(words & ctx_words) / len(words))
    return best


_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_NEGATION = re.compile(r"\b(not|no|never|cannot|can't|isn't|aren't|doesn't|don't|won't)\b", re.IGNORECASE)


def facts_consistent(sentence: str, contexts: list[str]) -> bool:
    """Targeted check for the item types where word overlap is too lenient.

    Stratified judge validation (evals/judge) showed the overlap check passing
    changed numbers and flipped negations, because they change one word and
    keep the rest. So: every number in the sentence must appear in the context,
    and the sentence must agree on negation with its best-matching context sentence.
    """
    ctx_numbers = {n for c in contexts for n in _NUMBER.findall(c)}
    if any(n not in ctx_numbers for n in _NUMBER.findall(sentence)):
        return False
    ctx_sentences = [s for c in contexts for s in split_sentences(c)]
    if not ctx_sentences:
        return True
    words = set(tokenize(sentence))
    best = max(ctx_sentences, key=lambda s: len(words & set(tokenize(s))))
    return bool(_NEGATION.search(sentence)) == bool(_NEGATION.search(best))


def groundedness(answer: str, contexts: list[str], threshold: float = 0.8,
                 check_facts: bool = True) -> tuple[float, list[str]]:
    """Fraction of answer sentences supported by the retrieved context.

    A sentence is supported when enough of its words appear in one context and,
    with ``check_facts`` (the default), its numbers and negations match too.
    Returns ``(score, unsupported_sentences)``. A refusal is trivially grounded.
    """
    sentences = split_sentences(strip_citations(answer))
    if not sentences:
        return 1.0, []
    unsupported = [s for s in sentences if sentence_support(s, contexts) < threshold
                   or (check_facts and not facts_consistent(s, contexts))]
    return 1 - len(unsupported) / len(sentences), unsupported


def retrieval_metrics(retrieved: list[str], expected: list[str]) -> dict[str, float]:
    """hit@k, recall@k and reciprocal rank for one query."""
    if not expected:
        return {"hit": 1.0, "recall": 1.0, "rr": 1.0}
    hits = [cid for cid in retrieved if cid in expected]
    rr = 0.0
    for rank, cid in enumerate(retrieved, start=1):
        if cid in expected:
            rr = 1 / rank
            break
    return {
        "hit": 1.0 if hits else 0.0,
        "recall": len(set(hits)) / len(set(expected)),
        "rr": rr,
    }


def contains_forbidden(answer: str, forbidden: list[str]) -> list[str]:
    norm_answer = normalize(answer)
    return [f for f in forbidden if normalize(f) in norm_answer]
