import pytest

from examples.ai_fundamentals.concepts import (
    bag_of_words_vector,
    cosine_similarity,
    estimate_cost_usd,
    estimate_tokens,
    fit_to_context,
    rank_documents,
)


@pytest.mark.parametrize("text, tokens", [("", 0), ("abcd", 1), ("abcde", 2), ("x" * 400, 100)])
def test_estimate_tokens(text, tokens):
    assert estimate_tokens(text) == tokens


def test_estimate_cost():
    # 1M input tokens at $1/M plus 500k output tokens at $4/M = $3
    assert estimate_cost_usd(1_000_000, 500_000, 1.0, 4.0) == 3.0


def test_fit_to_context_drops_what_does_not_fit():
    chunks = ["a" * 40, "b" * 40, "c" * 40]  # 10 tokens each
    assert fit_to_context(chunks, budget_tokens=25) == chunks[:2]
    assert fit_to_context(chunks, budget_tokens=25, reserved_for_answer=10) == chunks[:1]


def test_identical_texts_have_similarity_one():
    v = bag_of_words_vector("refund within 30 days")
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_ranking_prefers_shared_vocabulary():
    docs = {"refund": "full refund within 30 days", "security": "two-factor authentication"}
    assert rank_documents("refund 30 days", docs)[0][0] == "refund"


def test_keyword_vectors_miss_synonyms():
    """This is the failure that real embeddings (and article 07) are about."""
    docs = {"refund": "full refund within 30 days"}
    assert rank_documents("money back", docs)[0][1] == 0.0
