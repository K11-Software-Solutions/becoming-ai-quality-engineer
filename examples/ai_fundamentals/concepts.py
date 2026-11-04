"""AI fundamentals you can poke at: tokens, context windows, and embeddings.

Everything here is a toy so it runs offline and you can read every line.
Real tokenizers (BPE) and embedding models behave differently in detail, but
the testing questions they raise are the same.

Run the demo:  python examples/ai_fundamentals/concepts.py
"""
from __future__ import annotations

import math
import re
from collections import Counter


# --- Tokens -----------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Rule of thumb for English: about 4 characters per token.

    Use the provider's tokenizer for real budgets; this is for quick estimates.
    """
    return max(1, math.ceil(len(text) / 4)) if text else 0


def estimate_cost_usd(input_tokens: int, output_tokens: int,
                      usd_per_m_input: float, usd_per_m_output: float) -> float:
    """Cost = tokens x price. Prices are per million tokens on most price sheets."""
    return round(input_tokens / 1e6 * usd_per_m_input + output_tokens / 1e6 * usd_per_m_output, 6)


# --- Context windows --------------------------------------------------------

def fit_to_context(chunks: list[str], budget_tokens: int, reserved_for_answer: int = 0) -> list[str]:
    """Keep chunks in rank order until the token budget is used up.

    Whatever does not fit is silently dropped: a common cause of 'the answer
    was in the docs but the model never saw it'.
    """
    remaining = budget_tokens - reserved_for_answer
    kept = []
    for chunk in chunks:
        cost = estimate_tokens(chunk)
        if cost > remaining:
            break
        kept.append(chunk)
        remaining -= cost
    return kept


# --- Embeddings and similarity ----------------------------------------------

def bag_of_words_vector(text: str) -> Counter[str]:
    """A toy 'embedding': word counts. Real embeddings are dense float vectors
    learned so that *meanings*, not just words, land close together."""
    return Counter(re.findall(r"[a-z0-9]+", text.lower()))


def cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    dot = sum(a[k] * b[k] for k in a.keys() & b.keys())
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0


def rank_documents(query: str, docs: dict[str, str]) -> list[tuple[str, float]]:
    q = bag_of_words_vector(query)
    scores = [(doc_id, round(cosine_similarity(q, bag_of_words_vector(text)), 3)) for doc_id, text in docs.items()]
    return sorted(scores, key=lambda s: -s[1])


if __name__ == "__main__":
    docs = {
        "refund": "A full refund is available within 30 days of payment.",
        "security": "Turn on two-factor authentication in security settings.",
    }
    print("tokens in a sentence:", estimate_tokens("How long do I have to request a refund?"))
    print("rank for 'refund within 30 days':", rank_documents("refund within 30 days", docs))
    # Vocabulary mismatch: same meaning, no shared words -> similarity 0.
    print("rank for 'money back':", rank_documents("can I get my money back", docs))
