"""DeepEval suite for the NimbusNotes RAG app.

Two layers:

1. Custom deterministic metrics (KeyFacts, Groundedness) that run offline,
   so this file passes in CI without any API key.
2. DeepEval's built-in LLM-judged metrics (Faithfulness, AnswerRelevancy,
   ContextualRecall). They need a judge model, so they are skipped unless
   OPENAI_API_KEY is set.

Run from the repo root:

    pytest evals/deepeval -v
    # or with DeepEval's runner and dashboard integration:
    deepeval test run evals/deepeval/test_deepeval_rag.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from app.rag import RAGPipeline
from evals import metrics

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "golden_qa.jsonl"
CASES = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
# Only cases that are expected to pass; documented known failures are excluded
# here and tracked in the main eval report instead.
FACT_CASES = [c for c in CASES if c.get("expected_facts") and not c.get("notes")]


class KeyFactsMetric(BaseMetric):
    """Pass when every expected fact appears in the actual output."""

    def __init__(self, facts: list[str], threshold: float = 1.0):
        self.facts = facts
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        ok, missing = metrics.contains_all_facts(test_case.actual_output, self.facts)
        found = len(self.facts) - len(missing)
        self.score = found / len(self.facts) if self.facts else 1.0
        self.reason = "all facts present" if ok else f"missing: {missing}"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):  # DeepEval uses this as the metric's display name
        return "Key Facts"


class GroundednessMetric(BaseMetric):
    """Share of output sentences supported by retrieval_context (token overlap)."""

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        self.score, unsupported = metrics.groundedness(test_case.actual_output, test_case.retrieval_context or [])
        self.reason = "all sentences supported" if not unsupported else f"unsupported: {unsupported}"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "Groundedness (token overlap)"


@pytest.fixture(scope="module")
def pipeline() -> RAGPipeline:
    return RAGPipeline.from_settings()


def make_test_case(pipeline: RAGPipeline, case: dict) -> LLMTestCase:
    resp = pipeline.ask(case["question"])
    return LLMTestCase(
        input=case["question"],
        actual_output=resp.answer,
        expected_output="; ".join(case.get("expected_facts", [])),
        retrieval_context=resp.contexts,
    )


@pytest.mark.parametrize("case", FACT_CASES, ids=[c["id"] for c in FACT_CASES])
def test_answers_contain_key_facts_and_are_grounded(pipeline, case):
    test_case = make_test_case(pipeline, case)
    assert_test(test_case, [KeyFactsMetric(case["expected_facts"]), GroundednessMetric()], run_async=False)


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="LLM-judged metrics need OPENAI_API_KEY")
@pytest.mark.parametrize("case", FACT_CASES[:5], ids=[c["id"] for c in FACT_CASES[:5]])
def test_llm_judged_metrics(pipeline, case):
    from deepeval.metrics import AnswerRelevancyMetric, ContextualRecallMetric, FaithfulnessMetric

    test_case = make_test_case(pipeline, case)
    assert_test(test_case, [
        FaithfulnessMetric(threshold=0.8),
        AnswerRelevancyMetric(threshold=0.7),
        ContextualRecallMetric(threshold=0.7),
    ])
