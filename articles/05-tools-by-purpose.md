# 05. Tools by Purpose: A Short, Focused Tool Kit

> **Series:** Becoming an AI Quality Engineer · [Index](../README.md#article-index) · Previous: [04](04-evaluation-skills.md) · Next: [06. Roadmap and Hands-On Project](06-roadmap-and-hands-on-project.md)

The AI tooling landscape is crowded and changes monthly. **You do not need to learn everything.** You need one tool for each job, and you should understand the job well enough that switching tools later is easy. This article covers five tools grouped by the problem they solve, and tells you which one to try first.

## Start here

> **If you only have one weekend:** use **pytest** for everything, write your first evals as plain pytest tests with deterministic metrics (like [`evals/metrics.py`](../evals/metrics.py)), and add **Promptfoo** when you want to compare prompts or models side by side. Add a tracing tool only when you start debugging a real model.

| Purpose | Use | Try first | Learn later |
|---|---|---|---|
| Application testing (unit, API, UI) | pytest + Playwright | **pytest** | Playwright when there is a UI |
| AI evaluations | Promptfoo, DeepEval | **Promptfoo** if you like config and CLI; **DeepEval** if you live in pytest | the other one, only if you need it |
| Tracing and experiments | Langfuse, LangSmith | **Langfuse** (open source, framework-agnostic) | LangSmith if your team uses LangChain/LangGraph |

What you can safely skip at first: building your own vector database, fine-tuning, agent frameworks, and every "AI testing platform" you see advertised. Learn the concepts with these five tools; the rest will make sense later.

---

## 1. Application testing: pytest and Playwright

**Problem they solve:** an AI feature is still software. The API contract, input validation, error handling, the UI and the glue code all need normal, deterministic tests. These tests should be fast, free and run on every commit.

**pytest** runs the unit, API and example tests in this repo (`tests/unit`, `tests/api`, `examples/`). It also runs the DeepEval suite, which is one reason it is the best first tool: you learn one runner and reuse it for evals.

**Playwright** drives a real browser. [`tests/ui/test_ui.py`](../tests/ui/test_ui.py) starts the app on a free port and checks that a user can ask a question and see a cited answer. Use role- and label-based locators (`get_by_label("Question")`, `get_by_role("button", name="Ask")`) and web-first assertions (`expect(...).to_contain_text(...)`), which wait automatically and avoid flaky sleeps.

```bash
pytest                      # unit + API + examples (fast, default)
python -m playwright install chromium
pytest -m ui                # browser tests
```

**Do not** assert on exact LLM wording in UI tests. Assert that an answer appeared, that sources are shown, that errors are handled. Leave answer quality to evals.

---

## 2. AI evaluations: Promptfoo and DeepEval

Both tools run a set of inputs through your system and score the outputs with assertions or metrics. They overlap a lot. Pick based on how you like to work.

### Promptfoo

**Problem it solves:** quickly answering "which prompt / model / config is better on these test cases?", with a matrix view, caching, and a large library of assertions, plus a built-in red-teaming mode for security testing.

- **How it feels:** YAML config + CLI (`npx promptfoo eval`) + local web viewer (`npx promptfoo view`). Runs on Node, but calls Python providers and assertions.
- **Strengths:** side-by-side comparison of prompts and models, declarative assertions (`icontains`, `not-icontains`, `latency`, `llm-rubric`, `factuality`), red-team plugins, works with any language via custom providers.
- **In this repo:** [`evals/promptfoo/promptfooconfig.yaml`](../evals/promptfoo/promptfooconfig.yaml) calls the RAG app through a Python provider and checks facts, refusals, injection leaks, groundedness (custom Python assertion) and latency. It runs offline with the fake model. [`promptfooconfig.llm-judge.yaml`](../evals/promptfoo/promptfooconfig.llm-judge.yaml) shows model-graded checks that need a key.

```bash
npx promptfoo@0.124.0 eval -c evals/promptfoo/promptfooconfig.yaml
npx promptfoo@0.124.0 view
```

Promptfoo 0.124 needs Node.js 22.22 or newer. If Python is not on `PATH` as `python`, set `PROMPTFOO_PYTHON` to your interpreter.

### DeepEval

**Problem it solves:** writing LLM evals as **pytest tests in Python**, with a library of ready-made metrics for RAG and agents (faithfulness, answer relevancy, contextual recall and precision, hallucination, tool correctness and more).

- **How it feels:** `LLMTestCase(input=..., actual_output=..., retrieval_context=...)` plus `assert_test(test_case, [metrics])` inside a normal test function.
- **Strengths:** pytest-native, rich RAG metrics, easy custom metrics via `BaseMetric`.
- **Watch out:** most built-in metrics use an LLM as the judge, so they need an API key, cost money and are not deterministic. Validate them against human labels (article 04, section 7).
- **In this repo:** [`evals/deepeval/test_deepeval_rag.py`](../evals/deepeval/test_deepeval_rag.py) has two custom deterministic metrics that run offline and in CI, plus `Faithfulness`, `AnswerRelevancy` and `ContextualRecall` tests that run only when `OPENAI_API_KEY` is set.

```bash
pip install -r requirements-evals.txt
pytest evals/deepeval -v
```

### Which one first?

- You think in **pytest and Python** → start with **DeepEval** (or plain pytest + your own metrics).
- You want to **compare prompts or models** quickly, or do **red teaming** → start with **Promptfoo**.
- Your team already uses one → use that one.

You will get 90% of the value from either. Learning both deeply is not a requirement for an AI QE role; understanding what a faithfulness metric measures, and when to distrust it, is.

---

## 3. Tracing and experiments: Langfuse or LangSmith

**Problem they solve:** when an answer is wrong in production or in an eval, you need to see exactly what happened: the retrieved chunks, the full prompt, the model's raw output, latency and cost per step. Tracing tools record that for every request and let you compare runs of a dataset across prompt or model versions (experiments).

This repo ships a tiny local tracer ([`app/tracing.py`](../app/tracing.py)) so you can learn the idea with no account: set `TRACE_FILE=traces/traces.jsonl` and read the JSON. A tracing platform gives you the same data with a UI, search, sharing, annotation queues for human labels, and dataset experiments.

### Langfuse (try first)

Open source, can be self-hosted, works with any framework. Wrapping functions with its decorator creates nested spans:

```python
# pip install langfuse ; set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
from langfuse import observe

@observe()
def retrieve(question: str): ...

@observe()
def ask(question: str):
    chunks = retrieve(question)
    ...
```

### LangSmith

From the LangChain team; the natural choice if your stack is LangChain or LangGraph, and it also works without them:

```python
# pip install langsmith ; set LANGSMITH_TRACING=true and LANGSMITH_API_KEY
from langsmith import traceable

@traceable(name="ask")
def ask(question: str): ...
```

SDK details change between versions, so treat these snippets as a sketch and check the current docs. Neither tool is needed to run anything in this repo.

### What to look at in a trace

1. **Retrieved chunks and scores:** was the right chunk there, and where did it rank?
2. **The exact prompt sent:** was anything truncated, mislabelled or injected?
3. **Raw model output** before post-processing.
4. **Latency and tokens per step:** where the time and money go.

---

## A sensible learning order

1. pytest for unit and API tests of the app (article 06, step 2).
2. Your own deterministic metrics in Python (article 04).
3. Promptfoo **or** DeepEval for a structured eval suite.
4. Playwright for the UI.
5. Local traces, then Langfuse or LangSmith once you use a real model.

---
Next: [06. Roadmap and Hands-On Project](06-roadmap-and-hands-on-project.md)
