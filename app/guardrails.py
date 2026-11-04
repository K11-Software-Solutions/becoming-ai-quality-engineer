"""Simple, readable guardrails against prompt injection.

Pattern lists are NOT a complete defence: attackers paraphrase. They are a
first layer that is easy to test. Article 03 explains why defence in depth
(least privilege, labelling untrusted content, output checks) matters more.
"""
from __future__ import annotations

import re

from app.text import split_sentences

_INJECTION_PATTERNS = [
    r"ignore (all |any )?(the |your )?(previous|prior|above|earlier) (instructions|rules|messages)",
    r"disregard (all |any )?(the )?(previous|prior|above|your) (instructions|rules)",
    r"(reveal|print|show|repeat|output) (me )?(your |the )?(system )?prompt",
    r"\bsystem (note|prompt|override)\b",
    r"\byou are now\b",
    r"\b(email|send|share|give)\b.{0,30}\bpassword",
    r"\bdeveloper mode\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def looks_like_injection(text: str) -> bool:
    return any(p.search(text) for p in _COMPILED)


def sanitize_context(text: str) -> tuple[str, list[str]]:
    """Drop sentences that look like instructions aimed at the model."""
    kept: list[str] = []
    removed: list[str] = []
    for sentence in split_sentences(text):
        (removed if looks_like_injection(sentence) else kept).append(sentence)
    return " ".join(kept), removed


def check_question(question: str, max_chars: int) -> str | None:
    """Return a reason string if the question should be blocked, else None."""
    if not question.strip():
        return "empty_question"
    if len(question) > max_chars:
        return "question_too_long"
    if looks_like_injection(question):
        return "prompt_injection"
    return None
