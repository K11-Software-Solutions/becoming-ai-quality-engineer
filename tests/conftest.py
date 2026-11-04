"""Shared fixtures. Everything here uses the fake LLM, so no API key is needed."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_DOCS_DIR
from app.llm import FakeLLM
from app.main import create_app
from app.rag import RAGPipeline
from app.retriever import BM25Retriever


@pytest.fixture(scope="session")
def retriever() -> BM25Retriever:
    return BM25Retriever.from_dir(DEFAULT_DOCS_DIR)


@pytest.fixture
def make_pipeline(retriever):
    """Factory fixture: build a pipeline with any fake behaviour or top_k."""

    def _make(behavior: str = "faithful", top_k: int = 3) -> RAGPipeline:
        return RAGPipeline(retriever=retriever, llm=FakeLLM(behavior), top_k=top_k)

    return _make


@pytest.fixture
def pipeline(make_pipeline) -> RAGPipeline:
    return make_pipeline()


@pytest.fixture
def client(pipeline) -> TestClient:
    return TestClient(create_app(pipeline))
