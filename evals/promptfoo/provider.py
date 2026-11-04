"""Promptfoo custom Python provider that calls the NimbusNotes RAG pipeline.

Promptfoo renders the prompt template (here just ``{{question}}``) and passes
the result to ``call_api``. We return the answer as ``output`` and the
retrieved context in ``metadata`` so assertions can inspect it.

Provider selection follows the same env vars as the app (LLM_PROVIDER, ...),
so the fake LLM is used by default and no API key is needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.rag import RAGPipeline  # noqa: E402

_pipeline: RAGPipeline | None = None


def _get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline.from_settings()
    return _pipeline


def call_api(prompt: str, options: dict, context: dict) -> dict:
    resp = _get_pipeline().ask(prompt)
    return {
        "output": resp.answer,
        "metadata": {
            "refused": resp.refused,
            "blocked": resp.blocked,
            "sources": resp.sources,
            "citations": resp.citations,
            "contexts": resp.contexts,
            "model": resp.model,
        },
    }
