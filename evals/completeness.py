"""Heuristic completeness grader (rubric v2, Part B): a 0-3 score and a pass/fail by risk tier.

Completeness asks whether a *grounded* answer includes what the user needs from
the context, judged against the question asked. This grader approximates the
rubric's scale clause by clause:

1. Split the context into clauses and keep those relevant to the question
   (sharing a content word with it). The clause sharing the most is the direct
   answer.
2. Score:
   - 0  the answer barely covers the direct-answer clause (it does not answer)
   - 1  a number or a negation in the relevant clauses is missing (C2: a limit,
        deadline or exception is gone, so a user could act wrongly)
   - 2  something else is missing: part of the direct answer, or another
        relevant clause (C3: a secondary detail)
   - 3  everything relevant is covered

Coverage counts content words, with inflections normalised ("supported" matches
"supports") and a few generic linking verbs ("delivered", "containing") ignored:
rewording how a fact is phrased is not an omission.

It is validated like the groundedness judge: against reviewer scores
(evals/judge/completeness_labels.jsonl), with graded agreement and agreement on
pass/fail after the tier threshold. It cannot tell which missing words matter
beyond numbers and negations, so a missing required step with no number in it
(an alternative method, a place to go) scores 2, not 1; and it cannot recognise
an approximation ("a month" for "30 days") as covering a number.
"""
from __future__ import annotations

import re

from app.text import expand_query, split_sentences, tokenize

THRESHOLDS = {"high": 3, "standard": 2}   # rubric v2, Part B (approved 2026-11-06)
ANSWERS_AT = 0.4      # direct-answer clause coverage below this: the question is not answered
COVERED_AT = 0.9      # clause coverage at or above this: the clause is fully covered

# Verbs that link facts rather than carry them: their absence from an answer is rewording, not omission.
GENERIC_VERBS = frozenset("deliver contain offer provide include come arrive make use".split())
NEGATION = re.compile(r"\b(not|no|never|cannot|can't|isn't|aren't|doesn't|don't|won't)\b|n't\b", re.I)
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _norm(word: str) -> str:
    for suffix in ("ing", "ed", "es"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            word = word[: -len(suffix)]
            break
    if len(word) > 4 and word.endswith("e"):
        word = word[:-1]       # deliver/delivered, require/required, support/supported line up
    return word


def content(text: str) -> set[str]:
    return {w for w in (_norm(t) for t in tokenize(text)) if w not in GENERIC_VERBS}


def clauses(text: str) -> list[str]:
    return [c.strip() for s in split_sentences(text) for c in s.split(";") if c.strip()]


def relevant_clauses(question: str, context: str) -> list[str]:
    """Relevant clauses, the direct answer (most overlap with the question) first."""
    q = {_norm(t) for t in expand_query(tokenize(question))}
    scored = [(len(q & content(c)), i, c) for i, c in enumerate(clauses(context))]
    kept = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))
    return [c for _, _, c in kept] or clauses(context)


def relevant_text(question: str, context: str) -> str:
    return " ".join(relevant_clauses(question, context))


def _cover(clause: str, answer_words: set[str]) -> float:
    needed = content(clause)
    return len(needed & answer_words) / len(needed) if needed else 1.0


def coverage(answer: str, question: str, context: str) -> float:
    """Share of the relevant content words the answer covers."""
    return _cover(relevant_text(question, context), content(answer))


def score(answer: str, question: str, context: str) -> int:
    found = relevant_clauses(question, context)
    words = content(answer)
    if _cover(found[0], words) < ANSWERS_AT:
        return 0
    text = " ".join(found)
    numbers_missing = set(NUMBER.findall(text)) - set(NUMBER.findall(answer))
    negation_missing = bool(NEGATION.search(text)) and not NEGATION.search(answer)
    if numbers_missing or negation_missing:
        return 1
    if all(_cover(c, words) >= COVERED_AT for c in found):
        return 3
    return 2


def passes(value: int, tier: str) -> bool:
    return value >= THRESHOLDS[tier]
