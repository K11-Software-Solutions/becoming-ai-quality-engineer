"""LLM clients: a deterministic fake for tests/CI, plus OpenAI and Anthropic.

Every client exposes the same tiny interface::

    client.generate(system: str, user: str) -> str

Keeping the interface this small is a testing decision: the RAG pipeline can
be tested with the fake, and swapping in a real model changes nothing else.
"""
from __future__ import annotations

import re
from typing import Protocol

import httpx

from app.config import Settings
from app.text import expand_query, split_sentences, tokenize

REFUSAL = "I don't know based on the NimbusNotes documentation."

_CONTEXT_LINE = re.compile(r"^\[(?P<id>[^\]]+)\] \(source: (?P<source>\w+)\) (?P<text>.+)$")


class LLMError(RuntimeError):
    """Raised when a model provider call fails."""


class LLMClient(Protocol):
    name: str

    def generate(self, system: str, user: str) -> str: ...


def parse_prompt(user: str) -> tuple[str, list[tuple[str, str, str]]]:
    """Pull the question and the context lines back out of the user prompt."""
    question = ""
    contexts: list[tuple[str, str, str]] = []
    in_context = False
    for line in user.splitlines():
        if line.strip() == "<context>":
            in_context = True
        elif line.strip() == "</context>":
            in_context = False
        elif in_context:
            m = _CONTEXT_LINE.match(line.strip())
            if m:
                contexts.append((m["id"], m["source"], m["text"]))
        elif line.startswith("Question:"):
            question = line[len("Question:"):].strip()
    return question, contexts


class FakeLLM:
    """A deterministic, offline stand-in for a real model.

    ``faithful``        extractive answers built only from the provided context,
                        refusing when the context does not cover the question.
    ``hallucinate``     the faithful answer plus an unsupported claim, and it
                        never refuses. Use it to watch groundedness evals fail.
    ``ignore_context``  ignores the context entirely. Use it to watch
                        correctness evals fail.
    """

    MIN_OVERLAP = 2

    def __init__(self, behavior: str = "faithful"):
        if behavior not in {"faithful", "hallucinate", "ignore_context"}:
            raise ValueError(f"unknown fake LLM behavior: {behavior}")
        self.behavior = behavior
        self.name = f"fake-llm:{behavior}"

    def generate(self, system: str, user: str) -> str:
        question, contexts = parse_prompt(user)
        if self.behavior == "ignore_context":
            return "Thanks for asking! Please contact NimbusNotes support for help with that."
        answer = self._extractive_answer(question, contexts)
        if self.behavior == "hallucinate":
            if answer == REFUSAL:
                return "Yes, NimbusNotes supports that on every plan at no extra cost."
            return answer + " Every plan also includes free 24/7 phone support."
        return answer

    def _extractive_answer(self, question: str, contexts: list[tuple[str, str, str]]) -> str:
        q_terms = set(expand_query(tokenize(question)))
        candidates: list[tuple[float, int, str, str]] = []
        for rank, (chunk_id, source, text) in enumerate(contexts):
            weight = 1.0 if source == "official" else 0.5
            for sentence in split_sentences(text):
                overlap = len(q_terms & set(tokenize(sentence)))
                if overlap:
                    candidates.append((overlap * weight - rank * 0.01, overlap, sentence, chunk_id))
        if not candidates:
            return REFUSAL
        candidates.sort(key=lambda c: -c[0])
        best_score, best_overlap, best_sentence, best_id = candidates[0]
        if best_overlap < self.MIN_OVERLAP:
            return REFUSAL
        parts = [f"{best_sentence} [{best_id}]"]
        # Add one supporting sentence: prefer a neighbour from the same chunk,
        # otherwise a strong sentence from another chunk.
        rest = [c for c in candidates[1:] if c[2] != best_sentence]
        same_chunk = [c for c in rest if c[3] == best_id]
        other = [c for c in rest if c[1] >= self.MIN_OVERLAP and c[0] >= best_score / 2]
        extra = (same_chunk or other)[:1]
        for _, _, sentence, chunk_id in extra:
            parts.append(f"{sentence} [{chunk_id}]")
        return " ".join(parts)


class OpenAIChatLLM:
    def __init__(self, api_key: str, model: str, timeout: float = 30.0):
        self.name = f"openai:{model}"
        self._model = model
        self._client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def generate(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = self._client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMError(f"OpenAI call failed: {exc}") from exc


class AnthropicLLM:
    def __init__(self, api_key: str, model: str, timeout: float = 30.0):
        self.name = f"anthropic:{model}"
        self._model = model
        self._client = httpx.Client(
            base_url="https://api.anthropic.com/v1",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=timeout,
        )

    def generate(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "max_tokens": 400,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        try:
            resp = self._client.post("/messages", json=payload)
            resp.raise_for_status()
            blocks = resp.json()["content"]
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        except (httpx.HTTPError, KeyError) as exc:
            raise LLMError(f"Anthropic call failed: {exc}") from exc


def get_llm(settings: Settings) -> LLMClient:
    provider = settings.llm_provider
    if provider == "fake":
        return FakeLLM(settings.fake_llm_behavior)
    if provider == "openai":
        if not settings.openai_api_key:
            raise LLMError("LLM_PROVIDER=openai but OPENAI_API_KEY is not set")
        return OpenAIChatLLM(settings.openai_api_key, settings.openai_model, settings.request_timeout_s)
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        return AnthropicLLM(settings.anthropic_api_key, settings.anthropic_model, settings.request_timeout_s)
    raise LLMError(f"unknown LLM_PROVIDER: {provider}")
