"""Heuristic completeness grader (rubric v2, Part B): a 0-3 score and a pass/fail by risk tier.

Completeness asks whether a *grounded* answer includes what the user needs from
the context, judged against the question asked. This grader approximates that:

1. Keep the context sentences relevant to the question (sharing a content word with it).
2. Measure how much of their content the answer covers.
3. Map coverage to the 0-3 scale.

It is deliberately simple and it is validated like the groundedness judge: against
reviewer scores (evals/judge/completeness_labels.jsonl), with graded agreement and
agreement on pass/fail after the tier threshold. Expect it to miss the rubric's
real distinction between a secondary detail (score 2) and a missing condition
(score 1): word coverage cannot tell which omitted words matter.
"""
from __future__ import annotations

from app.text import expand_query, split_sentences, tokenize

THRESHOLDS = {"high": 3, "standard": 2}   # rubric v2, Part B (approved 2026-11-06)
CUTS = ((0.9, 3), (0.7, 2), (0.4, 1))    # coverage -> score


def relevant_text(question: str, context: str) -> str:
    q = set(expand_query(tokenize(question)))
    sentences = [s for s in split_sentences(context) if q & set(tokenize(s))]
    return " ".join(sentences) if sentences else context


def coverage(answer: str, question: str, context: str) -> float:
    needed = set(tokenize(relevant_text(question, context)))
    if not needed:
        return 1.0
    return len(needed & set(tokenize(answer))) / len(needed)


def score(answer: str, question: str, context: str) -> int:
    c = coverage(answer, question, context)
    for cut, value in CUTS:
        if c >= cut:
            return value
    return 0


def passes(value: int, tier: str) -> bool:
    return value >= THRESHOLDS[tier]
