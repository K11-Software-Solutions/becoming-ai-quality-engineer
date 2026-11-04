import pytest

from app.config import DEFAULT_DOCS_DIR
from app.retriever import BM25Retriever, load_chunks
from app.text import expand_query, split_sentences, stem, tokenize


@pytest.mark.parametrize("word, expected", [
    ("plans", "plan"),
    ("policies", "policy"),
    ("access", "access"),  # 'ss' endings are left alone
    ("is", "is"),
])
def test_stem(word, expected):
    assert stem(word) == expected


def test_tokenize_lowercases_and_drops_stopwords():
    assert tokenize("How do I EXPORT my Notes?") == ["export", "note"]


def test_expand_query_adds_synonyms():
    assert "refund" in expand_query(["money", "back"])


def test_split_sentences():
    assert split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]


def test_chunks_have_stable_ids_and_trust_labels():
    chunks = load_chunks(DEFAULT_DOCS_DIR)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"
    assert "refund-policy#1" in ids
    community = [c for c in chunks if c.doc_id == "community-forum-post"]
    assert community and not any(c.trusted for c in community)
    assert all(c.trusted for c in chunks if c.doc_id == "refund-policy")


@pytest.mark.parametrize("query, expected_top", [
    ("full refund within 30 days", "refund-policy#1"),
    ("Team plan minimum users", "pricing-plans#4"),
    ("429 Too Many Requests", "api-rate-limits#3"),
    ("conflict copy two devices", "offline-sync#2"),
])
def test_retriever_ranks_the_obvious_chunk_first(retriever, query, expected_top):
    results = retriever.search(query, k=3)
    assert results[0].chunk.chunk_id == expected_top


def test_retriever_respects_k_and_sorts_by_score(retriever):
    results = retriever.search("plan", k=2)
    assert len(results) == 2
    assert results[0].score >= results[1].score


def test_retriever_returns_nothing_for_unrelated_query(retriever):
    assert retriever.search("cryptocurrency blockchain", k=3) == []


def test_retriever_rejects_empty_corpus():
    with pytest.raises(ValueError):
        BM25Retriever([])
