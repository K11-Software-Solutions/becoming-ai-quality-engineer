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


def groundedness(answer: str, contexts: list[str], threshold: float = 0.8) -> tuple[float, list[str]]:
    """Fraction of answer sentences supported by the retrieved context.

    Returns ``(score, unsupported_sentences)``. A refusal is trivially grounded.
    """
    sentences = split_sentences(strip_citations(answer))
    if not sentences:
        return 1.0, []
    unsupported = [s for s in sentences if sentence_support(s, contexts) < threshold]
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
