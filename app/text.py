"""Tiny text utilities shared by the retriever and the fake LLM.

Real systems use proper tokenizers and embedding models. These helpers are
deliberately simple so you can read every line and predict their behaviour,
which is exactly what you want when you are learning to test them.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

STOPWORDS = frozenset(
    """a an and are as at be by can do does for from has have how i if in is it
    its my of on or our so that the their them then there these this to was we
    what when where which who will with you your me am any all get got about
    after before into not no yes than too very just also only up out much many
    long there nimbusnotes nimbusnote""".split()
)

# Query-side synonym expansion: a cheap stand-in for semantic search.
# Retrieval misses caused by vocabulary mismatch are a classic RAG failure;
# this table is how this toy app patches a few of them (see article 07).
SYNONYMS: dict[str, tuple[str, ...]] = {
    "money": ("refund",),
    "reimburse": ("refund",),
    "reimbursement": ("refund",),
    "price": ("cost", "plan"),
    "pricing": ("cost", "plan"),
    "expensive": ("cost",),
    "erase": ("deletion", "delete"),
    "remove": ("deletion", "delete"),
    "throttle": ("limit", "429"),
    "throttled": ("limit", "429"),
    "mfa": ("2fa", "two", "factor"),
    "locked": ("lock",),
    "internet": ("offline", "connection"),
    "download": ("export",),
    "discount": ("off", "percent"),
}


def stem(word: str) -> str:
    """Very rough stemmer: enough to match 'plans' with 'plan'."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text: str, drop_stopwords: bool = True) -> list[str]:
    tokens = [stem(t) for t in _WORD.findall(text.lower())]
    if drop_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens


def expand_query(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(SYNONYMS.get(token, ()))
    return expanded


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text.strip()) if s.strip()]
